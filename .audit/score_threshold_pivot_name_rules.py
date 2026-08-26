#!/usr/bin/env python3
"""Score the frozen 2021 pivot-geometry family. Throwaway. Cannot promote."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-pivot-stage1.json"
STAGE1_BRIEF = REPO / ".audit/briefs/threshold-pivot-stage1.md"
COVERING_BRIEF = (
    REPO / ".audit/briefs/threshold-covering-after-tape-kill-out.md"
)
STAGE0_RECEIPT = REPO / ".audit/threshold-pivot-stage0.json"
FEATURE_RANK_RECEIPT = REPO / ".audit/threshold-feature-rank.json"
THRESHOLD_BLOCK = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/"
    "evaluation/E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json"
)
PIVOT_ROOT = REPO / "artifacts/cache/port/entry_v2/g1/pivot"
CHECK = "python3 .audit/score_threshold_pivot_name_rules.py"
SCHEMA = "QRE2THRESHOLDPIVOTSTAGE11"
LABEL = (
    "eight frozen causal pivot-geometry name rules on the 2021 THRESHOLD "
    "block, plus the exploratory hindsight envelope_pivot8 family bound. "
    "Teacher-cash can kill and cannot promote."
)
RULE = (
    "On every joinable 20210721 through 20210806 dense-store THRESHOLD "
    "asset-day, join each CLEAR G1 candidate to its lowest fired "
    "QRE2G1PIVOT1 rung. Apply the eight frozen pivot-geometry rules with "
    "ties on maximum decision_ts_ns then smallest candidate_id. Pick one "
    "contract per cell. Cash is cert_close_usd on READY. The hindsight "
    "envelope enters only a positive READY pick. A 2021 clear promotes nothing."
)
PEEK_NOTE = (
    "Candidate-side inputs widen to G1's own pre-decision confirmation state. "
    "Teacher parse stays candidate_id, status, cert_close_usd, exit_ts_ns. "
    "This is a kill instrument and cannot promote."
)
WORKERS = 14
WINDOW_START_D8 = 20210721
WINDOW_END_D8 = 20210806
MUTANT = os.environ.get("QRE2_PIVOT_MUTANT", "")
MUTANTS = (
    "post_flip_leg_used_as_feature",
    "missing_tag_accepted",
    "envelope_includes_non_positive_cell",
)
RULES = {
    "pivot_leg_with": "Argmax of side times (pivot_mid2 - leg_start_mid2).",
    "pivot_leg_against": "Argmin of side times (pivot_mid2 - leg_start_mid2).",
    "pivot_retrace_max": (
        "Argmax of abs(pivot_mid2 - conf_mid2) divided by "
        "abs(pivot_mid2 - leg_start_mid2)."
    ),
    "pivot_retrace_min": (
        "Argmin of abs(pivot_mid2 - conf_mid2) divided by "
        "abs(pivot_mid2 - leg_start_mid2)."
    ),
    "pivot_age_max": "Argmax of decision_ts_ns - pivot_ts_recv_ns.",
    "pivot_age_min": "Argmin of decision_ts_ns - pivot_ts_recv_ns.",
    "pivot_legdur_max": (
        "Argmax of pivot_ts_recv_ns - leg_start_ts_recv_ns."
    ),
    "pivot_legdur_min": (
        "Argmin of pivot_ts_recv_ns - leg_start_ts_recv_ns."
    ),
}
RULE_SPECS = (
    ("pivot_leg_with", "leg_aligned", True),
    ("pivot_leg_against", "leg_aligned", False),
    ("pivot_retrace_max", "retrace", True),
    ("pivot_retrace_min", "retrace", False),
    ("pivot_age_max", "pivot_age_ns", True),
    ("pivot_age_min", "pivot_age_ns", False),
    ("pivot_legdur_max", "leg_duration_ns", True),
    ("pivot_legdur_min", "leg_duration_ns", False),
)
RULE_NAMES = tuple(name for name, _field, _want_max in RULE_SPECS)
PIVOT_COLUMNS = (
    "candidate_id",
    "asset",
    "d8",
    "rung_index",
    "side",
    "pivot_mid2",
    "pivot_ts_recv_ns",
    "pivot_ordinal",
    "leg_start_mid2",
    "leg_start_ts_recv_ns",
    "leg_start_ordinal",
    "conf_mid2",
    "threshold_mid2_raw",
)
CANDIDATE_EXTRA_COLUMNS = ("side", "entry_mid2", "rung_mask")


def _load_module(name: str) -> ModuleType:
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_feature = _load_module("score_threshold_feature_rank.py")
_killed = _feature._killed
_ceiling = _feature._ceiling
_gap = _feature._gap

ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
RUNGS_USD = _killed.RUNGS_USD
DRAWDOWN_LIMIT_USD = _killed.DRAWDOWN_LIMIT_USD
ENTRY_CAP = _killed.ENTRY_CAP
JoinUnavailable = _killed.JoinUnavailable
SelectedName = _killed.SelectedName
CANDIDATE_COLUMNS = _killed.CANDIDATE_COLS + CANDIDATE_EXTRA_COLUMNS
TEACHER_COLUMNS = _killed.TEACHER_COLS
PEEK_COLUMNS = _killed.PEEK_COLS
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
SOURCE_RECEIPTS = _killed.RECEIPTS
DENSE_STORE = _feature.DENSE
summarize_line = _ceiling.summarize_line
pick_cell_best_ready = _ceiling.pick_cell_best_ready
enter_positive = _ceiling.enter_positive
ready_rows = _ceiling._ready_rows
as_selected = _ceiling._as_selected
join_picked = _gap._join_picked
load_teacher = _killed._load_teacher
relative = _killed._relative
receipt_output_sha256 = _killed._receipt_output_sha256


@dataclass(frozen=True, slots=True)
class ThresholdShard:
    asset: str
    d8: int
    identity: str
    manifest: Path
    artifact: Path


@dataclass(frozen=True, slots=True)
class CandidateRow:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    side: int
    entry_mid2: int
    rung_mask: int


@dataclass(frozen=True, slots=True)
class PivotTag:
    candidate_id: str
    rung_index: int
    side: int
    pivot_mid2: int
    pivot_ts_recv_ns: int
    pivot_ordinal: int
    leg_start_mid2: int
    leg_start_ts_recv_ns: int
    leg_start_ordinal: int
    conf_mid2: int
    threshold_mid2_raw: int


@dataclass(frozen=True, slots=True)
class PivotName:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    side: int
    entry_mid2: int
    pivot: PivotTag


@dataclass(frozen=True, slots=True)
class PivotScore:
    row: PivotName
    leg_aligned: float
    retrace: float
    pivot_age_ns: float
    leg_duration_ns: float


@dataclass(frozen=True, slots=True)
class RulePicks:
    causal: Mapping[str, tuple[PivotName, ...]]
    twins: Mapping[tuple[str, int, int], PivotName]
    twin_matches: Mapping[str, int]
    cells: int


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    picks: Mapping[str, tuple[object, ...]]
    envelope: tuple[object, ...]
    twin_matches: Mapping[str, int]
    twin_cells: int
    envelope_twin_matches: int
    envelope_twin_cells: int
    source_identity: Mapping[str, object]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise JoinUnavailable(label, f"missing JSON artifact {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise JoinUnavailable(label, f"cannot parse JSON artifact {path}") from exc
    if not isinstance(value, dict):
        raise JoinUnavailable(
            label,
            f"{path} payload type {type(value).__name__} expected object",
        )
    return value


def _source_file(path: Path) -> dict[str, object]:
    return {"path": relative(path), "sha256": _sha256_file(path)}


def _verified_output(path: Path, receipt: Path) -> str:
    expected = receipt_output_sha256(receipt)
    actual = _sha256_file(path)
    if actual != expected:
        raise JoinUnavailable(
            "source.output_sha256",
            f"{path} sha256 {actual!r} differs from {receipt} output_sha256 "
            f"{expected!r}",
        )
    return actual


def _normalized_shard_sources(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list):
        raise JoinUnavailable(
            "feature_rank.sources.shards",
            f"feature-rank shards type {type(rows).__name__} expected list",
        )
    normalized: list[dict[str, object]] = []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise JoinUnavailable(
                "feature_rank.sources.shards",
                f"feature-rank shard {index} type {type(raw).__name__} expected object",
            )
        normalized.append(
            {
                "asset": str(raw.get("asset")),
                "d8": int(raw.get("d8", 0)),
                "identity": str(raw.get("identity")),
                "path": str(raw.get("path")),
            }
        )
    return sorted(normalized, key=lambda row: (int(row["d8"]), str(row["asset"])))


def _threshold_roster() -> tuple[
    tuple[ThresholdShard, ...], dict[str, object], dict[str, int]
]:
    block = _read_json_object(THRESHOLD_BLOCK, "threshold_block")
    block_tag = block.get("name")
    if block.get("schema") != "QRE2TABPOLICYBLOCK2":
        raise JoinUnavailable(
            "threshold_block.schema",
            f"{THRESHOLD_BLOCK} schema {block.get('schema')!r} "
            "expected QRE2TABPOLICYBLOCK2",
        )
    if block_tag != "E1R_raw_THRESHOLD":
        raise JoinUnavailable(
            "threshold_block.tag",
            f"{THRESHOLD_BLOCK} block tag {block_tag!r} expected E1R_raw_THRESHOLD",
        )
    if block.get("bounds") != [WINDOW_START_D8, WINDOW_END_D8]:
        raise JoinUnavailable(
            "threshold_block.bounds",
            f"{THRESHOLD_BLOCK} bounds {block.get('bounds')!r} expected "
            f"{[WINDOW_START_D8, WINDOW_END_D8]!r}",
        )
    expected_sessions = block.get("expected_sessions")
    if not isinstance(expected_sessions, list):
        raise JoinUnavailable(
            "threshold_block.expected_sessions",
            f"{THRESHOLD_BLOCK} expected_sessions must be a list",
        )
    block_keys: set[tuple[str, int]] = set()
    for index, raw in enumerate(expected_sessions):
        if not isinstance(raw, dict):
            raise JoinUnavailable(
                "threshold_block.expected_sessions",
                f"{THRESHOLD_BLOCK} expected session {index} is not an object",
            )
        key = (str(raw.get("asset")), int(raw.get("trading_day", 0)))
        if key in block_keys:
            raise JoinUnavailable(
                "threshold_block.expected_sessions",
                f"{THRESHOLD_BLOCK} repeats expected session {key!r}",
            )
        block_keys.add(key)

    feature_rank = _read_json_object(FEATURE_RANK_RECEIPT, "feature_rank_receipt")
    if feature_rank.get("schema") != "QRE2THRESHOLDFEATURERANK1":
        raise JoinUnavailable(
            "feature_rank_receipt.schema",
            f"{FEATURE_RANK_RECEIPT} schema {feature_rank.get('schema')!r} "
            "expected QRE2THRESHOLDFEATURERANK1",
        )
    if feature_rank.get("window") != ["2021-07-21", "2021-08-06"]:
        raise JoinUnavailable(
            "feature_rank_receipt.window",
            f"{FEATURE_RANK_RECEIPT} window {feature_rank.get('window')!r} changed",
        )
    sources = feature_rank.get("sources")
    if not isinstance(sources, dict):
        raise JoinUnavailable(
            "feature_rank_receipt.sources",
            f"{FEATURE_RANK_RECEIPT} sources must be an object",
        )
    expected_shards = _normalized_shard_sources(sources.get("shards"))
    discovered = _feature.discover_window_shards()
    actual_shards = sorted(
        (
            {
                "asset": ref.asset,
                "d8": ref.d8,
                "identity": ref.identity,
                "path": relative(ref.artifact),
            }
            for ref in discovered.values()
        ),
        key=lambda row: (int(row["d8"]), str(row["asset"])),
    )
    if actual_shards != expected_shards:
        raise JoinUnavailable(
            "dense_store.block_roster",
            "dense-store THRESHOLD roster differs from threshold-feature-rank",
        )

    shards: list[ThresholdShard] = []
    for raw in actual_shards:
        asset = str(raw["asset"])
        d8 = int(raw["d8"])
        identity = str(raw["identity"])
        artifact = REPO / str(raw["path"])
        manifest = artifact.with_suffix(".json")
        metadata = _read_json_object(manifest, "dense_store.metadata")
        if metadata.get("schema") != "QRE2TABDENSEFEATURECACHE1":
            raise JoinUnavailable(
                "dense_store.metadata.schema",
                f"{manifest} schema {metadata.get('schema')!r} "
                "expected QRE2TABDENSEFEATURECACHE1",
            )
        if metadata.get("identity_sha256") != identity:
            raise JoinUnavailable(
                "dense_store.metadata.identity",
                f"{manifest} identity {metadata.get('identity_sha256')!r} "
                f"expected {identity!r}",
            )
        recorded_artifact = Path(str(metadata.get("artifact_path")))
        if recorded_artifact.resolve() != artifact.resolve():
            raise JoinUnavailable(
                "dense_store.metadata.artifact",
                f"{manifest} artifact {recorded_artifact} expected {artifact}",
            )
        if (asset, d8) not in block_keys:
            raise JoinUnavailable(
                "dense_store.block_tag",
                f"dense-store shard {asset}/{d8} is absent from {block_tag}",
            )
        shards.append(ThresholdShard(asset, d8, identity, manifest, artifact))

    lines = feature_rank.get("lines")
    argmax = lines.get("argmax") if isinstance(lines, dict) else None
    expected_days = argmax.get("days") if isinstance(argmax, dict) else None
    if not isinstance(expected_days, dict):
        raise JoinUnavailable(
            "feature_rank_receipt.days",
            f"{FEATURE_RANK_RECEIPT} lacks lines.argmax.days",
        )
    days = {asset: int(expected_days.get(asset, -1)) for asset in ASSETS}
    if any(value < 0 for value in days.values()):
        raise JoinUnavailable(
            "feature_rank_receipt.days",
            f"{FEATURE_RANK_RECEIPT} days {days!r} are invalid",
        )
    block_source = {
        **_source_file(THRESHOLD_BLOCK),
        "schema": block.get("schema"),
        "tag": block_tag,
        "bounds": block.get("bounds"),
    }
    return tuple(shards), block_source, days


def _stage0_tag_hashes() -> tuple[dict[tuple[str, int], str], dict[str, object]]:
    receipt = _read_json_object(STAGE0_RECEIPT, "stage0_receipt")
    if (
        receipt.get("schema") != "QRE2G1PIVOTSTAGE01"
        or receipt.get("status") != "PASS"
    ):
        raise JoinUnavailable(
            "stage0_receipt.status",
            f"{STAGE0_RECEIPT} schema/status "
            f"{(receipt.get('schema'), receipt.get('status'))!r} expected PASS",
        )
    if receipt.get("emitted_2022_2024_tags") is not False:
        raise JoinUnavailable(
            "stage0_receipt.era_tags",
            f"{STAGE0_RECEIPT} emitted_2022_2024_tags must be false",
        )
    guard = receipt.get("determinism_guard")
    per_asset = guard.get("per_asset") if isinstance(guard, dict) else None
    if not isinstance(per_asset, dict):
        raise JoinUnavailable(
            "stage0_receipt.determinism_guard",
            f"{STAGE0_RECEIPT} lacks determinism_guard.per_asset",
        )
    hashes: dict[tuple[str, int], str] = {}
    for asset in ASSETS:
        asset_guard = per_asset.get(asset)
        raw_hashes = (
            asset_guard.get("threshold_tag_sha256s")
            if isinstance(asset_guard, dict)
            else None
        )
        if not isinstance(raw_hashes, dict):
            raise JoinUnavailable(
                "stage0_receipt.threshold_tag_sha256s",
                f"{STAGE0_RECEIPT} lacks {asset} threshold tag hashes",
            )
        for raw_d8, raw_hash in raw_hashes.items():
            d8 = int(raw_d8)
            if WINDOW_START_D8 <= d8 <= WINDOW_END_D8:
                hashes[(asset, d8)] = str(raw_hash)
    source = {
        **_source_file(STAGE0_RECEIPT),
        "schema": receipt.get("schema"),
        "status": receipt.get("status"),
    }
    return hashes, source


def _load_candidates(
    asset: str, d8: int
) -> tuple[int, tuple[CandidateRow, ...], set[str], Path | None]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return 0, (), set(), None
    _killed._assert_no_peek(CANDIDATE_COLUMNS, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(CANDIDATE_COLUMNS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "phase": np.int64,
            "decision_ts_ns": np.int64,
            "compliance_status": str,
            "frozen_cost_usd": np.float64,
            "side": np.int64,
            "entry_mid2": np.int64,
            "rung_mask": np.int64,
        },
    )
    n_rows = int(len(frame))
    if n_rows == 0:
        return 0, (), set(), path
    if set(frame["asset"].unique()) - {asset}:
        raise JoinUnavailable(
            "candidates.asset",
            f"{path} asset values {sorted(frame['asset'].unique())} expected {asset}",
        )
    if set(frame["d8"].unique()) - {d8}:
        raise JoinUnavailable(
            "candidates.d8",
            f"{path} d8 values {sorted(int(v) for v in frame['d8'].unique())} "
            f"expected {d8}",
        )
    all_ids = set(frame["candidate_id"].astype(str))
    if len(all_ids) != n_rows:
        raise JoinUnavailable(
            "candidates.candidate_id",
            f"{path} has {n_rows - len(all_ids)} repeated candidate_id rows",
        )
    clear = frame[frame["compliance_status"] == "CLEAR"]
    rows: list[CandidateRow] = []
    for raw in clear.to_dict(orient="records"):
        candidate_id = str(raw["candidate_id"])
        side = int(raw["side"])
        rung_mask = int(raw["rung_mask"])
        if side not in (-1, 1):
            raise JoinUnavailable(
                "candidates.side",
                f"{path} candidate {candidate_id!r} side {side!r} expected -1 or 1",
            )
        if rung_mask <= 0:
            raise JoinUnavailable(
                "candidates.rung_mask",
                f"{path} candidate {candidate_id!r} rung_mask {rung_mask!r} "
                "expected positive",
            )
        rows.append(
            CandidateRow(
                candidate_id=candidate_id,
                asset=str(raw["asset"]),
                d8=int(raw["d8"]),
                phase=int(raw["phase"]),
                decision_ts_ns=int(raw["decision_ts_ns"]),
                frozen_cost_usd=float(raw["frozen_cost_usd"]),
                side=side,
                entry_mid2=int(raw["entry_mid2"]),
                rung_mask=rung_mask,
            )
        )
    return n_rows, tuple(rows), all_ids, path


def _pivot_schema_line(path: Path, d8: int) -> None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            line = handle.readline().strip()
    except (OSError, UnicodeError) as exc:
        raise JoinUnavailable("pivot.path", f"cannot read pivot tag {path}") from exc
    expected = (
        "# QRE2G1PIVOT1 start_d8=20210101 end_d8_exclusive=20210807 "
        f"d8={d8}"
    )
    if line != expected:
        raise JoinUnavailable(
            "pivot.schema",
            f"{path} schema line {line!r} expected {expected!r}",
        )


def _load_pivot_tags(
    asset: str,
    d8: int,
    all_candidate_ids: set[str],
    expected_sha256: str,
) -> tuple[dict[str, PivotTag], Path, str]:
    path = PIVOT_ROOT / asset / f"{d8}.tsv"
    if not path.is_file():
        raise JoinUnavailable("pivot.path", f"missing pivot tag {path}")
    actual_sha256 = _sha256_file(path)
    if actual_sha256 != expected_sha256:
        raise JoinUnavailable(
            "pivot.sha256",
            f"{path} sha256 {actual_sha256!r} differs from Stage 0 "
            f"{expected_sha256!r}",
        )
    _pivot_schema_line(path, d8)
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(PIVOT_COLUMNS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "rung_index": np.int64,
            "side": np.int64,
            "pivot_mid2": np.int64,
            "pivot_ts_recv_ns": np.int64,
            "pivot_ordinal": np.int64,
            "leg_start_mid2": np.int64,
            "leg_start_ts_recv_ns": np.int64,
            "leg_start_ordinal": np.int64,
            "conf_mid2": np.int64,
            "threshold_mid2_raw": np.int64,
        },
    )
    if not frame.empty:
        if set(frame["asset"].unique()) - {asset}:
            raise JoinUnavailable(
                "pivot.asset",
                f"{path} asset values {sorted(frame['asset'].unique())} expected {asset}",
            )
        if set(frame["d8"].unique()) - {d8}:
            raise JoinUnavailable(
                "pivot.d8",
                f"{path} d8 values {sorted(int(v) for v in frame['d8'].unique())} "
                f"expected {d8}",
            )
    tags: dict[str, PivotTag] = {}
    seen_rungs: set[tuple[str, int]] = set()
    for raw in frame.to_dict(orient="records"):
        candidate_id = str(raw["candidate_id"])
        rung_index = int(raw["rung_index"])
        key = (candidate_id, rung_index)
        if key in seen_rungs:
            raise JoinUnavailable(
                "pivot.rung_index",
                f"{path} repeats candidate/rung {key!r}",
            )
        seen_rungs.add(key)
        tag = PivotTag(
            candidate_id=candidate_id,
            rung_index=rung_index,
            side=int(raw["side"]),
            pivot_mid2=int(raw["pivot_mid2"]),
            pivot_ts_recv_ns=int(raw["pivot_ts_recv_ns"]),
            pivot_ordinal=int(raw["pivot_ordinal"]),
            leg_start_mid2=int(raw["leg_start_mid2"]),
            leg_start_ts_recv_ns=int(raw["leg_start_ts_recv_ns"]),
            leg_start_ordinal=int(raw["leg_start_ordinal"]),
            conf_mid2=int(raw["conf_mid2"]),
            threshold_mid2_raw=int(raw["threshold_mid2_raw"]),
        )
        prior = tags.get(candidate_id)
        if prior is None or tag.rung_index < prior.rung_index:
            tags[candidate_id] = tag
    unknown = sorted(set(tags) - all_candidate_ids)
    if unknown:
        raise JoinUnavailable(
            "pivot.candidate_id",
            f"{path} has {len(unknown)} tags absent from candidates, first {unknown[0]!r}",
        )
    return tags, path, actual_sha256


def _join_candidates_tags(
    candidates: Sequence[CandidateRow],
    tags: Mapping[str, PivotTag],
    source: str,
) -> tuple[PivotName, ...]:
    rows: list[PivotName] = []
    for candidate in candidates:
        tag = tags.get(candidate.candidate_id)
        if tag is None:
            if MUTANT == "missing_tag_accepted":
                continue
            raise JoinUnavailable(
                "pivot.candidate_id",
                f"{source} candidate {candidate.candidate_id!r} has no pivot tag",
            )
        lowest_fired = (candidate.rung_mask & -candidate.rung_mask).bit_length() - 1
        if tag.rung_index != lowest_fired:
            raise JoinUnavailable(
                "pivot.rung_index",
                f"{source} candidate {candidate.candidate_id!r} lowest tag "
                f"{tag.rung_index} expected fired rung {lowest_fired}",
            )
        if tag.side != candidate.side:
            raise JoinUnavailable(
                "pivot.side",
                f"{source} candidate {candidate.candidate_id!r} pivot side "
                f"{tag.side} differs from candidate side {candidate.side}",
            )
        rows.append(
            PivotName(
                candidate_id=candidate.candidate_id,
                asset=candidate.asset,
                d8=candidate.d8,
                phase=candidate.phase,
                decision_ts_ns=candidate.decision_ts_ns,
                frozen_cost_usd=candidate.frozen_cost_usd,
                side=candidate.side,
                entry_mid2=candidate.entry_mid2,
                pivot=tag,
            )
        )
    return tuple(rows)


def _score_name(row: PivotName) -> PivotScore:
    tag = row.pivot
    leg_start_mid2 = (
        tag.conf_mid2
        if MUTANT == "post_flip_leg_used_as_feature"
        else tag.leg_start_mid2
    )
    leg_size = abs(tag.pivot_mid2 - leg_start_mid2)
    if leg_size == 0:
        raise JoinUnavailable(
            "pivot.leg_size",
            f"candidate {row.candidate_id!r} pivot {tag.pivot_mid2} and "
            f"leg start {leg_start_mid2} produce zero leg size",
        )
    pivot_age_ns = row.decision_ts_ns - tag.pivot_ts_recv_ns
    if pivot_age_ns < 0:
        raise JoinUnavailable(
            "pivot.age",
            f"candidate {row.candidate_id!r} pivot age {pivot_age_ns} expected nonnegative",
        )
    return PivotScore(
        row=row,
        leg_aligned=float(row.side * (tag.pivot_mid2 - leg_start_mid2)),
        retrace=float(abs(tag.pivot_mid2 - tag.conf_mid2) / leg_size),
        pivot_age_ns=float(pivot_age_ns),
        leg_duration_ns=float(
            tag.pivot_ts_recv_ns - tag.leg_start_ts_recv_ns
        ),
    )


def _pick_score(
    rows: Sequence[PivotScore], field: str, want_max: bool
) -> PivotName:
    if not rows:
        raise JoinUnavailable("pivot.cell", "cannot pick from an empty pivot cell")

    def key(row: PivotScore) -> tuple[float, int, str]:
        value = float(getattr(row, field))
        primary = -value if want_max else value
        return primary, -row.row.decision_ts_ns, row.row.candidate_id

    return min(rows, key=key).row


def _pick_entry_price_twin(rows: Sequence[PivotName]) -> PivotName:
    if not rows:
        raise JoinUnavailable("pivot.cell", "cannot pick twin from an empty cell")
    return min(
        rows,
        key=lambda row: (
            -float(row.side * row.entry_mid2),
            -row.decision_ts_ns,
            row.candidate_id,
        ),
    )


def _pick_rules(rows: Sequence[PivotName]) -> RulePicks:
    by_cell: dict[tuple[str, int, int], list[PivotName]] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    picked: dict[str, list[PivotName]] = {name: [] for name in RULE_NAMES}
    matches = {name: 0 for name in RULE_NAMES}
    twins: dict[tuple[str, int, int], PivotName] = {}
    for cell in sorted(by_cell):
        scores = tuple(_score_name(row) for row in by_cell[cell])
        twin = _pick_entry_price_twin(by_cell[cell])
        twins[cell] = twin
        for name, field, want_max in RULE_SPECS:
            winner = _pick_score(scores, field, want_max)
            picked[name].append(winner)
            matches[name] += int(winner.candidate_id == twin.candidate_id)
    return RulePicks(
        causal={name: tuple(picked[name]) for name in RULE_NAMES},
        twins=twins,
        twin_matches=matches,
        cells=len(by_cell),
    )


def _envelope(
    causal: Mapping[str, Sequence[PivotName]],
    teacher: Mapping[str, tuple[str, float, int]],
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    unique = {
        row.candidate_id: row
        for name in RULE_NAMES
        for row in causal[name]
    }
    ready = ready_rows(
        tuple(unique[candidate_id] for candidate_id in sorted(unique)),
        teacher,
        "envelope_pivot8",
    )
    best = pick_cell_best_ready(ready)
    entered = (
        best
        if MUTANT == "envelope_includes_non_positive_cell"
        else enter_positive(best)
    )
    return best, entered


def _empty_picks() -> dict[str, tuple[object, ...]]:
    return {name: () for name in RULE_NAMES}


def _score_asset_day(
    shard: ThresholdShard, expected_tag_sha256: str
) -> DayBundle:
    asset = shard.asset
    d8 = shard.d8
    n_rows, candidates, all_ids, candidate_path = _load_candidates(asset, d8)
    dense_source = {
        "identity": shard.identity,
        "metadata": _source_file(shard.manifest),
        "artifact_path": relative(shard.artifact),
    }
    if candidate_path is None or n_rows == 0:
        return DayBundle(
            asset,
            d8,
            False,
            _empty_picks(),
            (),
            {name: 0 for name in RULE_NAMES},
            0,
            0,
            0,
            {"asset": asset, "d8": d8, "dense_store": dense_source},
        )
    candidate_receipt = SOURCE_RECEIPTS / asset / f"{d8}.candidates.json"
    candidate_sha256 = _verified_output(candidate_path, candidate_receipt)
    tags, pivot_path, pivot_sha256 = _load_pivot_tags(
        asset, d8, all_ids, expected_tag_sha256
    )
    joined = _join_candidates_tags(candidates, tags, relative(pivot_path))
    source_identity: dict[str, object] = {
        "asset": asset,
        "d8": d8,
        "dense_store": dense_source,
        "candidates": {
            "path": relative(candidate_path),
            "receipt": relative(candidate_receipt),
            "sha256": candidate_sha256,
        },
        "pivot": {
            "path": relative(pivot_path),
            "sha256": pivot_sha256,
            "lowest_fired_rung_rows": len(tags),
        },
    }
    if not joined:
        return DayBundle(
            asset,
            d8,
            True,
            _empty_picks(),
            (),
            {name: 0 for name in RULE_NAMES},
            0,
            0,
            0,
            source_identity,
        )
    wanted = [row.candidate_id for row in joined]
    teacher, teacher_path = load_teacher(asset, d8, wanted)
    teacher_receipt = SOURCE_RECEIPTS / asset / f"{d8}.teacher.json"
    teacher_sha256 = _verified_output(teacher_path, teacher_receipt)
    source_identity["teacher"] = {
        "path": relative(teacher_path),
        "receipt": relative(teacher_receipt),
        "sha256": teacher_sha256,
    }
    selected = _pick_rules(joined)
    relative_candidate = relative(candidate_path)
    relative_teacher = relative(teacher_path)
    picks = {
        name: join_picked(
            selected.causal[name],
            teacher,
            relative_candidate,
            relative_teacher,
            candidate_sha256,
            teacher_sha256,
        )
        for name in RULE_NAMES
    }
    envelope_best, envelope_entered = _envelope(selected.causal, teacher)
    envelope_entries = as_selected(
        envelope_entered,
        relative_candidate,
        relative_teacher,
        candidate_sha256,
        teacher_sha256,
    )
    envelope_matches = 0
    for row in envelope_best:
        cell = (row.asset, row.d8, row.phase)
        twin = selected.twins.get(cell)
        envelope_matches += int(
            twin is not None and row.candidate_id == twin.candidate_id
        )
    return DayBundle(
        asset=asset,
        d8=d8,
        joinable=True,
        picks=picks,
        envelope=envelope_entries,
        twin_matches=selected.twin_matches,
        twin_cells=selected.cells,
        envelope_twin_matches=envelope_matches,
        envelope_twin_cells=len(envelope_best),
        source_identity=source_identity,
    )


def _score_job(item: tuple[ThresholdShard, str]) -> DayBundle:
    return _score_asset_day(*item)


def _window_line(bundles: Sequence[DayBundle], name: str) -> object:
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    for bundle in bundles:
        if not bundle.joinable:
            continue
        days[bundle.asset] += 1
        if name == "envelope_pivot8":
            entries.extend(bundle.envelope)
        else:
            entries.extend(bundle.picks[name])
    return summarize_line(entries, days)


def _clears_full_threshold(line: object) -> bool:
    return bool(
        line.trades > 0
        and line.clears_rungs
        and line.max_drawdown_usd < DRAWDOWN_LIMIT_USD
        and line.entry_cap_ok
        and line.overlap_violations == 0
    )


def _line_payload(
    line: object, twin_matches: int, twin_cells: int
) -> dict[str, object]:
    value = line.as_dict()
    value["clears_stage1_dollar_gate"] = bool(line.trades > 0 and line.clears_rungs)
    value["clears_full_threshold"] = _clears_full_threshold(line)
    value["entry_price_twin_matches"] = twin_matches
    value["entry_price_twin_cells"] = twin_cells
    value["entry_price_twin_match_rate"] = (
        twin_matches / twin_cells if twin_cells else 0.0
    )
    return value


def _stage1_stop_text() -> str:
    text = COVERING_BRIEF.read_text()
    start_marker = "- **KILL at stage 1.**"
    end_marker = "\n- **RUNGS at stage 2.**"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise JoinUnavailable(
            "covering_stop",
            f"{COVERING_BRIEF} lacks Stage 1 stop markers {start!r}, {end!r}",
        )
    return text[start:end].strip()


def dollar_stop(
    lines: Mapping[str, object], envelope: object
) -> dict[str, object]:
    hits = [
        name
        for name in RULE_NAMES
        if lines[name].trades > 0 and lines[name].clears_rungs
    ]
    envelope_clears = bool(envelope.trades > 0 and envelope.clears_rungs)
    verdict = "not-KILL" if hits or envelope_clears else "KILL"
    if hits:
        applied = (
            f"not-KILL because causal lines {hits} clear the 2021 dollar rungs. "
            "This promotes nothing and only unlocks Stage 2."
        )
    elif envelope_clears:
        applied = (
            "not-KILL because envelope_pivot8 clears the 2021 dollar rungs. "
            "This promotes nothing and only unlocks Stage 2."
        )
    else:
        applied = (
            "KILL because all eight causal lines and envelope_pivot8 miss the "
            "2021 dollar rungs. The unfitted pivot-geometry family is closed."
        )
    return {
        "verdict": verdict,
        "causal_lines_clearing": hits,
        "envelope_pivot8_clears": envelope_clears,
        "rungs_usd": dict(RUNGS_USD),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "entry_cap": ENTRY_CAP,
        "required_trades_min": 1,
        "required_overlap_violations": 0,
        "applied": applied,
        "verbatim": _stage1_stop_text(),
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if MUTANT:
        raise JoinUnavailable(
            "mutant",
            f"window run refuses QRE2_PIVOT_MUTANT={MUTANT!r}",
        )
    if tuple(TEACHER_COLUMNS) != (
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    ):
        raise JoinUnavailable(
            "teacher.usecols",
            f"teacher usecols {TEACHER_COLUMNS!r} changed from the frozen four columns",
        )
    if any(name in CANDIDATE_COLUMNS for name in PEEK_COLUMNS):
        raise JoinUnavailable(
            "candidates.usecols",
            "pivot-name candidate usecols include peek columns",
        )
    if any(name in TEACHER_COLUMNS for name in PEEK_COLUMNS):
        raise JoinUnavailable(
            "teacher.usecols",
            "pivot-name teacher usecols include peek columns",
        )
    if len(RULE_NAMES) != 8:
        raise JoinUnavailable(
            "causal_lines",
            f"pivot causal line count {len(RULE_NAMES)} expected 8",
        )

    shards, block_source, expected_days = _threshold_roster()
    tag_hashes, stage0_source = _stage0_tag_hashes()
    jobs: list[tuple[ThresholdShard, str]] = []
    for shard in shards:
        expected_hash = tag_hashes.get((shard.asset, shard.d8))
        if expected_hash is None:
            raise JoinUnavailable(
                "stage0_receipt.threshold_tag_sha256s",
                f"Stage 0 lacks tag hash for {shard.asset}/{shard.d8}",
            )
        jobs.append((shard, expected_hash))
    jobs.sort(key=lambda item: (item[0].d8, item[0].asset))
    bundles: list[DayBundle] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for bundle in pool.map(_score_job, jobs):
            bundles.append(bundle)

    lines = {name: _window_line(bundles, name) for name in RULE_NAMES}
    envelope = _window_line(bundles, "envelope_pivot8")
    days = lines[RULE_NAMES[0]].days
    if days != expected_days:
        raise JoinUnavailable(
            "threshold.days",
            f"pivot-name days {days} differ from sibling 2021 days {expected_days}",
        )
    if any(line.days != expected_days for line in lines.values()):
        raise JoinUnavailable(
            "threshold.days",
            "pivot-name causal lines disagree on 2021 denominators",
        )
    if envelope.days != expected_days:
        raise JoinUnavailable(
            "envelope_pivot8.days",
            f"envelope days {envelope.days} differ from {expected_days}",
        )
    twin_matches = {
        name: sum(int(bundle.twin_matches[name]) for bundle in bundles)
        for name in RULE_NAMES
    }
    twin_cells = sum(bundle.twin_cells for bundle in bundles)
    envelope_twin_matches = sum(
        bundle.envelope_twin_matches for bundle in bundles
    )
    envelope_twin_cells = sum(bundle.envelope_twin_cells for bundle in bundles)
    stop = dollar_stop(lines, envelope)
    verdict = str(stop["verdict"])
    return {
        "schema": SCHEMA,
        "status": verdict,
        "verdict": verdict,
        "label": LABEL,
        "window": ["2021-07-21", "2021-08-06"],
        "block_tag": block_source["tag"],
        "rule": RULE,
        "rules": dict(RULES),
        "causal_lines": list(RULE_NAMES),
        "tie_break": ["max decision_ts_ns", "smallest candidate_id"],
        "peek_note": PEEK_NOTE,
        "candidate_columns": list(CANDIDATE_COLUMNS),
        "teacher_columns": list(TEACHER_COLUMNS),
        "pivot_columns": list(PIVOT_COLUMNS),
        "pivot_rung_selection": "lowest fired rung_index per candidate_id",
        "lines": {
            name: _line_payload(lines[name], twin_matches[name], twin_cells)
            for name in RULE_NAMES
        },
        "envelope_pivot8": _line_payload(
            envelope, envelope_twin_matches, envelope_twin_cells
        ),
        "dollar_stop": stop,
        "n_dense_feature_bytes_read": 0,
        "n_era_bytes_read": 0,
        "n_forecast_rows_read": 0,
        "workers": WORKERS,
        "wall_clock_sec": wall_clock_sec,
        "verification_commands": {
            "selftest": f"{CHECK} --selftest",
            "mutants": [
                f"QRE2_PIVOT_MUTANT={name} {CHECK} --selftest"
                for name in MUTANTS
            ],
        },
        "sources": {
            "script": _source_file(Path(__file__)),
            "stage1_brief": _source_file(STAGE1_BRIEF),
            "covering_brief": _source_file(COVERING_BRIEF),
            "stage0_receipt": stage0_source,
            "feature_rank_receipt": {
                **_source_file(FEATURE_RANK_RECEIPT),
                "schema": "QRE2THRESHOLDFEATURERANK1",
            },
            "threshold_block": block_source,
            "dense_store_root": relative(DENSE_STORE),
            "candidates_root": relative(CANDIDATES),
            "teacher_root": relative(TEACHERS),
            "pivot_root": relative(PIVOT_ROOT),
            "receipts_root": relative(SOURCE_RECEIPTS),
            "joined_artifacts": [
                dict(bundle.source_identity)
                for bundle in sorted(
                    bundles, key=lambda row: (row.d8, row.asset)
                )
            ],
        },
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _fixture_candidate(
    candidate_id: str,
    decision_ts_ns: int,
    side: int,
    entry_mid2: int,
    phase: int = 0,
) -> CandidateRow:
    return CandidateRow(
        candidate_id=candidate_id,
        asset="HG",
        d8=20210721,
        phase=phase,
        decision_ts_ns=decision_ts_ns,
        frozen_cost_usd=5.0,
        side=side,
        entry_mid2=entry_mid2,
        rung_mask=1,
    )


def _fixture_tag(
    candidate_id: str,
    side: int,
    pivot_mid2: int,
    leg_start_mid2: int,
    conf_mid2: int,
    pivot_ts_recv_ns: int,
    leg_start_ts_recv_ns: int,
) -> PivotTag:
    return PivotTag(
        candidate_id=candidate_id,
        rung_index=0,
        side=side,
        pivot_mid2=pivot_mid2,
        pivot_ts_recv_ns=pivot_ts_recv_ns,
        pivot_ordinal=20,
        leg_start_mid2=leg_start_mid2,
        leg_start_ts_recv_ns=leg_start_ts_recv_ns,
        leg_start_ordinal=10,
        conf_mid2=conf_mid2,
        threshold_mid2_raw=10,
    )


def _fixture_name(
    candidate_id: str,
    decision_ts_ns: int,
    side: int,
    entry_mid2: int,
    pivot_mid2: int,
    leg_start_mid2: int,
    conf_mid2: int,
    pivot_ts_recv_ns: int,
    leg_start_ts_recv_ns: int,
    phase: int = 0,
) -> PivotName:
    candidate = _fixture_candidate(
        candidate_id, decision_ts_ns, side, entry_mid2, phase
    )
    tag = _fixture_tag(
        candidate_id,
        side,
        pivot_mid2,
        leg_start_mid2,
        conf_mid2,
        pivot_ts_recv_ns,
        leg_start_ts_recv_ns,
    )
    return _join_candidates_tags((candidate,), {candidate_id: tag}, "selftest")[0]


def _selected(
    candidate_id: str, asset: str, cash_usd: float, decision_ts_ns: int
) -> object:
    return SelectedName(
        candidate_id,
        asset,
        20210721,
        0,
        decision_ts_ns,
        5.0,
        cash_usd,
        decision_ts_ns + 1,
        True,
        "",
        "",
        "",
        "",
    )


def _selftest() -> int:
    if MUTANT not in ("", *MUTANTS):
        raise AssertionError(f"selftest unknown mutant {MUTANT!r}")
    if len(RULE_NAMES) != 8:
        raise AssertionError(f"selftest causal line count {len(RULE_NAMES)} != 8")
    if tuple(TEACHER_COLUMNS) != (
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    ):
        raise AssertionError(f"selftest teacher columns {TEACHER_COLUMNS!r}")
    if any(name in CANDIDATE_COLUMNS for name in PEEK_COLUMNS):
        raise AssertionError("selftest candidate usecols parse peek columns")
    if any(name in TEACHER_COLUMNS for name in PEEK_COLUMNS):
        raise AssertionError("selftest teacher usecols parse peek columns")

    a = _fixture_name("a", 1000, 1, 50, 120, 100, 118, 900, 700)
    b = _fixture_name("b", 1001, 1, 60, 115, 105, 107, 800, 750)
    picks = _pick_rules((a, b))
    expected = {
        "pivot_leg_with": "a",
        "pivot_leg_against": "b",
        "pivot_retrace_max": "b",
        "pivot_retrace_min": "a",
        "pivot_age_max": "b",
        "pivot_age_min": "a",
        "pivot_legdur_max": "a",
        "pivot_legdur_min": "b",
    }
    actual = {
        name: picks.causal[name][0].candidate_id for name in RULE_NAMES
    }
    if actual != expected:
        raise AssertionError(f"selftest pivot picks {actual!r} != {expected!r}")
    if picks.twins[("HG", 20210721, 0)].candidate_id != "b":
        raise AssertionError(f"selftest entry-price twin {picks.twins!r}")

    earlier = _fixture_name("z", 10, 1, 10, 20, 10, 15, 5, 1)
    later_b = _fixture_name("b", 20, 1, 10, 20, 10, 15, 5, 1)
    later_a = _fixture_name("a", 20, 1, 10, 20, 10, 15, 5, 1)
    tied = tuple(_score_name(row) for row in (earlier, later_b, later_a))
    tie_pick = _pick_score(tied, "leg_aligned", True)
    if tie_pick.candidate_id != "a":
        raise AssertionError(f"selftest tie chain picked {tie_pick.candidate_id!r}")

    candidate_a = _fixture_candidate("a", 1000, 1, 50)
    candidate_b = _fixture_candidate("b", 1001, 1, 60)
    tag_a = _fixture_tag("a", 1, 120, 100, 118, 900, 700)
    try:
        _join_candidates_tags(
            (candidate_a, candidate_b), {"a": tag_a}, "selftest-missing"
        )
    except JoinUnavailable:
        pass
    else:
        raise AssertionError("selftest accepted a candidate with no pivot tag")

    low = _fixture_name("low", 30, 1, 10, 20, 10, 15, 5, 1)
    high = _fixture_name("high", 40, 1, 20, 30, 10, 20, 6, 1)
    negative = _fixture_name(
        "negative", 50, 1, 30, 40, 10, 20, 7, 1, phase=1
    )
    causal = {
        name: ((low, negative) if index < 4 else (high, negative))
        for index, name in enumerate(RULE_NAMES)
    }
    teacher = {
        "low": ("READY", 5.0, 31),
        "high": ("READY", 10.0, 41),
        "negative": ("READY", -1.0, 51),
    }
    envelope_best, envelope_entered = _envelope(causal, teacher)
    if [row.candidate_id for row in envelope_best] != ["high", "negative"]:
        raise AssertionError(f"selftest envelope best {envelope_best!r}")
    if [row.candidate_id for row in envelope_entered] != ["high"]:
        raise AssertionError(
            f"selftest envelope included a non-positive cell {envelope_entered!r}"
        )

    empty = summarize_line((), {"HG": 1, "NKD": 1, "SI": 1})
    misses = {name: empty for name in RULE_NAMES}
    killed = dollar_stop(misses, empty)
    if killed["verdict"] != "KILL":
        raise AssertionError(f"selftest KILL {killed!r}")
    clear = summarize_line(
        (
            _selected("hg", "HG", 2000.0, 10),
            _selected("nkd", "NKD", 1500.0, 11),
            _selected("si", "SI", 1500.0, 12),
        ),
        {"HG": 1, "NKD": 1, "SI": 1},
    )
    hits = {name: empty for name in RULE_NAMES}
    hits["pivot_leg_with"] = clear
    survived = dollar_stop(hits, empty)
    if (
        survived["verdict"] != "not-KILL"
        or survived["causal_lines_clearing"] != ["pivot_leg_with"]
    ):
        raise AssertionError(f"selftest not-KILL {survived!r}")
    print("selftest_ok zero_era_bytes=1")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--selftest" in args:
        if args != ["--selftest"]:
            raise ValueError(f"--selftest must be the only argument, got {args}")
        return _selftest()
    if args:
        raise ValueError(f"unsupported arguments {args}")
    started = time.perf_counter()
    receipt = build_receipt(0.0)
    receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    _write_receipt(receipt)
    usd = {
        name: receipt["lines"][name]["usd_per_asset_day"] for name in RULE_NAMES
    }
    print(
        f"receipt={relative(RECEIPT)} verdict={receipt['verdict']} "
        f"causal_lines_clearing={receipt['dollar_stop']['causal_lines_clearing']} "
        f"envelope_pivot8_clears="
        f"{receipt['dollar_stop']['envelope_pivot8_clears']} "
        f"usd_per_asset_day={usd}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
