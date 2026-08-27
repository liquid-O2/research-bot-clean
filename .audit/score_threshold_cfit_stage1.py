#!/usr/bin/env python3
"""Run the frozen C Stage 1 causal CatBoost name fit."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-cfit-stage1.json"
COVERING_BRIEF = REPO / ".audit/briefs/threshold-covering-after-pivot-kill-out.md"
STAGE0_RECEIPT = REPO / ".audit/threshold-cfit-stage0.json"
STAGE0_JUDGE = REPO / ".audit/briefs/threshold-cfit-stage0-judge-out.md"
FREEZE = REPO / ".audit/threshold-2022-2024-freeze.md"
PIVOT_ROOT = REPO / "artifacts/cache/port/entry_v2/g1/pivot"
CHECK = "python3 .audit/score_threshold_cfit_stage1.py"
SCHEMA = "QRE2THRESHOLDCFITSTAGE11"
WINDOW_START = "2022-03-09"
WINDOW_END = "2024-12-31"
WINDOW_START_D8 = 20220309
WINDOW_END_D8 = 20241231
WORKERS = 13
TRIPWIRE_SECONDS = 7200.0
CATBOOST_VERSION = "1.2.10"
RANDOM_SEED = 20260826
MUTANT = os.environ.get("QRE2_CFIT_MUTANT", "")
MUTANTS = (
    "future_train_leak",
    "day_outcome_as_feature",
    "missing_tag_accepted",
)
GUARD_MUTANT = "corrupt_candidate_id_accepted"
KNOWN_MUTANTS = frozenset((*MUTANTS, GUARD_MUTANT))

NUMERIC_FEATURES = (
    "leg_signed",
    "retrace_ratio",
    "threshold_frac",
    "pivot_age_ns",
    "legdur_ns",
    "events_in_leg",
    "events_since_pivot",
    "rung_index",
    "n_rungs_fired",
    "time_rank",
    "frozen_cost_usd",
    "entry_spread_usd",
    "compliance_distance_sec",
    "sane_ceiling_usd",
    "atr14_prev_usd",
    "entry_mid2",
    "side",
    "confirmation_event_ordinal",
    "prefix_last_event_ordinal",
    "spread_prior_usd",
    "spread_prior_present",
    "recency",
)
CATEGORICAL_FEATURES = ("rung_mask", "delay")
FEATURES = (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)
BANNED_FEATURES = (
    "cert_close_usd",
    "status",
    "exit_ts_ns",
    "mfe_usd",
    "mae_usd",
    "payer",
    "take_target",
)
CANDIDATE_COLUMNS = (
    "candidate_id",
    "asset",
    "d8",
    "confirmation_event_ordinal",
    "decision_ts_ns",
    "side",
    "phase",
    "rung_mask",
    "delay",
    "prefix_last_event_ordinal",
    "entry_mid2",
    "entry_spread_usd",
    "frozen_cost_usd",
    "atr14_prev_usd",
    "spread_prior_present",
    "spread_prior_usd",
    "sane_ceiling_usd",
    "compliance_status",
    "compliance_distance_sec",
)
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
TEACHER_COLUMNS = ("candidate_id", "status", "cert_close_usd", "exit_ts_ns")
PEEK_NOTE = (
    "Candidate-side inputs are stored candidate columns plus G1's own "
    "pre-decision confirmation state. Teacher parse stays candidate_id, "
    "status, cert_close_usd, exit_ts_ns. mfe_usd, mae_usd, payer, and "
    "take_target stay unparsed. Training consumes outcomes only from days "
    "strictly before the day being scored. This fit can kill and cannot promote."
)
RULE = (
    "Per asset and gated day D, fit CatBoost on every joinable CLEAR candidate "
    "from 2022-03-09 through the day strictly before D, using both gate states. "
    "The binary target marks the maximum READY cert_close_usd name in each "
    "cell, and cells with no READY name do not train. Score D's CLEAR names, "
    "pick the maximum score, then maximum decision_ts_ns, then smallest "
    "candidate_id. An empty or positive-free training set falls back to the "
    "earliest CLEAR name. Evaluation uses the frozen day gate and locked "
    "denominators. One contract enters per cell, and READY cert_close_usd is cash."
)
RUNGS_VERBATIM = (
    "- **RUNGS at stage 1.** The fitted pick posts, on the locked gated "
    "denominators, trades > 0, HG >= 2000, NKD >= 1500, SI >= 1500 "
    "`usd_per_asset_day`, `max_drawdown_usd` < 1000, at most 12 entries per "
    "portfolio day, overlap 0, dollars per trade. Next unit, pre-written: "
    "freeze the per-day model artifacts and the rule text, then the one "
    "`QRE2TABPOLICYBLOCK2` engine walk that exits "
    "`python3 .audit/assert_threshold_replay_receipt.py` at 0, per "
    "`.audit/threshold-2022-2024-freeze.md` and ticket 48. A teacher pass is "
    "still not THRESHOLD."
)
KILL_VERBATIM = (
    "- **KILL at stage 1.** The fitted pick misses any rung or fails any other "
    "line. Then fitted identity at age 180 is closed on every plane this host "
    "carries: the scanned-8 by fit-name, the 2021 matrix by feature-rank, the "
    "tape by its own unfired mixture clause, and geometry plus discretes plus "
    "instruments by this receipt. The age-180 name-identity program closes "
    "with it. The remaining live fork is B alone, late ages, whose first unit "
    "is a late-age cell-best ceiling measurement, labels before pickers, "
    "authorized by a new covering decision and not by this stop. D stays a "
    "component. The 37-residue histograms stay parked. No second config, no "
    "seed sweep, no feature widening, no per-asset resurrection."
)


def _load_module(filename: str) -> ModuleType:
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_ceiling = _load_module("score_threshold_2022_2024_ceiling.py")
_base = _ceiling._killed
ASSETS = _base.ASSETS
PHASES = _base.PHASES
RUNGS_USD = _base.RUNGS_USD
DRAWDOWN_LIMIT_USD = _base.DRAWDOWN_LIMIT_USD
ENTRY_CAP = _base.ENTRY_CAP
EXPECTED_GATED_DAYS = _ceiling.EXPECTED_GATED_DAYS
CANDIDATES = _base.CANDIDATES
TEACHERS = _base.TEACHERS
SOURCE_RECEIPTS = _base.RECEIPTS
FORECAST = _base.FORECAST
JoinUnavailable = _base.JoinUnavailable
SelectedName = _base.SelectedName

try:
    import catboost
    from catboost import CatBoostClassifier
except ImportError as exc:
    catboost = None
    CatBoostClassifier = None
    CATBOOST_IMPORT_ERROR: ImportError | None = exc
else:
    CATBOOST_IMPORT_ERROR = None


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    selected: bool
    joinable: bool
    frame: pd.DataFrame
    sources: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class AssetDataset:
    asset: str
    frame: pd.DataFrame
    days: Mapping[int, DayBundle]


@dataclass(frozen=True, slots=True)
class FitResult:
    asset: str
    d8: int
    chosen_indices: tuple[int, ...]
    training_rows: int
    training_positive_rows: int
    training_cells: int
    evaluation_cells: int
    fallback_no_train: bool
    twin_matches: int
    twin_cells: int
    fit_seconds: float


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise JoinUnavailable("source.path", f"cannot hash source {path}") from exc
    return digest.hexdigest()


def _source_file(path: Path) -> dict[str, str]:
    return {"path": _relative(path), "sha256": _sha256_file(path)}


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


def _verify_file_sha(path: Path, expected: str, label: str) -> str:
    actual = _sha256_file(path)
    if actual != expected and MUTANT != GUARD_MUTANT:
        raise JoinUnavailable(
            label,
            f"{path} sha256 {actual!r} expected {expected!r}",
        )
    return actual


def _verified_output(
    path: Path,
    receipt: Path,
    label: str,
) -> tuple[str, str, str]:
    payload = _read_json_object(receipt, f"{label}.receipt")
    expected = payload.get("output_sha256")
    if not isinstance(expected, str) or not expected:
        raise JoinUnavailable(
            f"{label}.output_sha256",
            f"{receipt} output_sha256 {expected!r} expected nonempty string",
        )
    actual = _verify_file_sha(path, expected, f"{label}.output_sha256")
    return actual, _sha256_file(receipt), expected


def _assert_feature_contract() -> None:
    actual = list(FEATURES)
    if MUTANT == "day_outcome_as_feature":
        actual.append("cert_close_usd")
    leaked = [name for name in actual if name in BANNED_FEATURES]
    if leaked:
        raise JoinUnavailable(
            "features",
            f"fitted features include forbidden outcome columns {leaked}",
        )
    expected = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]
    if actual != expected:
        raise JoinUnavailable(
            "features",
            f"feature order {actual!r} differs from frozen order {expected!r}",
        )
    if set(TEACHER_COLUMNS) != {
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    }:
        raise JoinUnavailable(
            "teacher.usecols",
            f"teacher columns changed to {TEACHER_COLUMNS!r}",
        )
    leaked_teacher = set(TEACHER_COLUMNS).intersection(_base.PEEK_COLS)
    if leaked_teacher:
        raise JoinUnavailable(
            "teacher.usecols",
            f"teacher usecols include peek columns {sorted(leaked_teacher)}",
        )


def _require_catboost() -> None:
    if CATBOOST_IMPORT_ERROR is not None or catboost is None or CatBoostClassifier is None:
        raise JoinUnavailable(
            "catboost.import",
            f"CatBoost 1.2.10 import failed: {CATBOOST_IMPORT_ERROR}",
        )
    if catboost.__version__ != CATBOOST_VERSION:
        raise JoinUnavailable(
            "catboost.version",
            f"CatBoost version {catboost.__version__!r} expected {CATBOOST_VERSION!r}",
        )


def _stage0_inputs() -> tuple[dict[str, dict[int, str]], dict[str, object]]:
    receipt = _read_json_object(STAGE0_RECEIPT, "stage0_receipt")
    if receipt.get("schema") != "QRE2THRESHOLDCFITSTAGE01":
        raise JoinUnavailable(
            "stage0_receipt.schema",
            f"{STAGE0_RECEIPT} schema {receipt.get('schema')!r} expected "
            "QRE2THRESHOLDCFITSTAGE01",
        )
    if receipt.get("status") != "PASS":
        raise JoinUnavailable(
            "stage0_receipt.status",
            f"{STAGE0_RECEIPT} status {receipt.get('status')!r} expected PASS",
        )
    window = receipt.get("window")
    expected_window = {
        "start_d8": 20210101,
        "existing_tag_end_d8_exclusive": 20210807,
        "new_tag_start_d8": 20210807,
        "era_start_d8": 20220101,
        "end_d8_exclusive": 20250101,
    }
    if window != expected_window:
        raise JoinUnavailable(
            "stage0_receipt.window",
            f"{STAGE0_RECEIPT} window {window!r} expected {expected_window!r}",
        )
    if receipt.get("fit_started") is not False or receipt.get("stage1_started") is not False:
        raise JoinUnavailable(
            "stage0_receipt.stage1_started",
            f"{STAGE0_RECEIPT} must precede every Stage 1 fit",
        )
    coverage = receipt.get("gated_era_tag_coverage")
    if not isinstance(coverage, dict) or coverage.get("status") != "PASS":
        raise JoinUnavailable(
            "stage0_receipt.gated_era_tag_coverage",
            f"{STAGE0_RECEIPT} gated era coverage is not PASS",
        )
    raw_sources = receipt.get("sources")
    if not isinstance(raw_sources, dict):
        raise JoinUnavailable(
            "stage0_receipt.sources",
            f"{STAGE0_RECEIPT} sources must be an object",
        )
    verified_sources: dict[str, str] = {}
    for raw_path, raw_sha in raw_sources.items():
        path = REPO / str(raw_path)
        expected = str(raw_sha)
        verified_sources[str(raw_path)] = _verify_file_sha(
            path,
            expected,
            "stage0_receipt.sources",
        )
    raw_tags = receipt.get("tag_sha256_manifest")
    if not isinstance(raw_tags, dict):
        raise JoinUnavailable(
            "stage0_receipt.tag_sha256_manifest",
            f"{STAGE0_RECEIPT} tag manifest must be an object",
        )
    tags: dict[str, dict[int, str]] = {}
    for asset in ASSETS:
        raw_asset = raw_tags.get(asset)
        if not isinstance(raw_asset, dict):
            raise JoinUnavailable(
                "stage0_receipt.tag_sha256_manifest",
                f"{STAGE0_RECEIPT} lacks {asset} tag hashes",
            )
        tags[asset] = {int(d8): str(sha) for d8, sha in raw_asset.items()}
    manifest_sha = receipt.get("manifest_sha256s")
    if not isinstance(manifest_sha, dict):
        raise JoinUnavailable(
            "stage0_receipt.manifest_sha256s",
            f"{STAGE0_RECEIPT} manifest_sha256s must be an object",
        )
    pivot_manifests: dict[str, dict[str, str]] = {}
    for asset in ASSETS:
        path = PIVOT_ROOT / asset / "manifest.tsv"
        expected = str(manifest_sha.get(asset, ""))
        actual = _verify_file_sha(path, expected, "pivot.manifest_sha256")
        pivot_manifests[asset] = {"path": _relative(path), "sha256": actual}
    source = {
        **_source_file(STAGE0_RECEIPT),
        "schema": receipt.get("schema"),
        "status": receipt.get("status"),
        "verified_source_sha256s": verified_sources,
        "pivot_manifests": pivot_manifests,
    }
    return tags, source


def _load_candidates(asset: str, d8: int) -> tuple[pd.DataFrame, dict[str, object]]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return pd.DataFrame(columns=CANDIDATE_COLUMNS), {}
    receipt = SOURCE_RECEIPTS / asset / f"{d8}.candidates.json"
    actual, receipt_sha, expected = _verified_output(path, receipt, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(CANDIDATE_COLUMNS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "confirmation_event_ordinal": np.int64,
            "decision_ts_ns": np.int64,
            "side": np.int64,
            "phase": np.int64,
            "rung_mask": np.int64,
            "delay": str,
            "prefix_last_event_ordinal": np.int64,
            "entry_mid2": np.int64,
            "entry_spread_usd": np.float64,
            "frozen_cost_usd": np.float64,
            "atr14_prev_usd": np.float64,
            "spread_prior_present": np.int64,
            "spread_prior_usd": np.float64,
            "sane_ceiling_usd": np.float64,
            "compliance_status": str,
            "compliance_distance_sec": np.float64,
        },
    )
    if set(frame.columns) != set(CANDIDATE_COLUMNS):
        raise JoinUnavailable(
            "candidates.columns",
            f"{path} parsed columns {frame.columns.tolist()} expected {list(CANDIDATE_COLUMNS)}",
        )
    if not frame.empty:
        assets = set(frame["asset"].astype(str))
        days = set(int(value) for value in frame["d8"])
        if assets != {asset} or days != {d8}:
            raise JoinUnavailable(
                "candidates.identity",
                f"{path} asset/d8 values {(sorted(assets), sorted(days))!r} "
                f"expected {(asset, d8)!r}",
            )
        ids = frame["candidate_id"].astype(str)
        if ids.duplicated().any():
            repeated = str(ids[ids.duplicated()].iloc[0])
            raise JoinUnavailable(
                "candidates.candidate_id",
                f"{path} repeats candidate_id {repeated!r}",
            )
    source = {
        "path": _relative(path),
        "sha256": actual,
        "receipt": _relative(receipt),
        "receipt_sha256": receipt_sha,
        "output_sha256": expected,
        "rows": int(len(frame)),
    }
    return frame, source


def _load_pivots(
    asset: str,
    d8: int,
    expected_sha: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    path = PIVOT_ROOT / asset / f"{d8}.tsv"
    if not path.is_file():
        raise JoinUnavailable("pivot.path", f"missing pivot tag {path}")
    actual = _verify_file_sha(path, expected_sha, "pivot.sha256")
    try:
        with path.open("r", encoding="utf-8") as handle:
            schema_line = handle.readline().strip()
    except (OSError, UnicodeError) as exc:
        raise JoinUnavailable("pivot.path", f"cannot read pivot tag {path}") from exc
    expected_line = (
        "# QRE2G1PIVOT1 start_d8=20210101 end_d8_exclusive=20250101 "
        f"d8={d8}"
    )
    if schema_line != expected_line:
        raise JoinUnavailable(
            "pivot.schema",
            f"{path} schema line {schema_line!r} expected {expected_line!r}",
        )
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
    if set(frame.columns) != set(PIVOT_COLUMNS):
        raise JoinUnavailable(
            "pivot.columns",
            f"{path} parsed columns {frame.columns.tolist()} expected {list(PIVOT_COLUMNS)}",
        )
    if not frame.empty:
        assets = set(frame["asset"].astype(str))
        days = set(int(value) for value in frame["d8"])
        if assets != {asset} or days != {d8}:
            raise JoinUnavailable(
                "pivot.identity",
                f"{path} asset/d8 values {(sorted(assets), sorted(days))!r} "
                f"expected {(asset, d8)!r}",
            )
        duplicated = frame.duplicated(subset=["candidate_id", "rung_index"])
        if duplicated.any():
            row = frame.loc[duplicated].iloc[0]
            raise JoinUnavailable(
                "pivot.rung_index",
                f"{path} repeats candidate/rung "
                f"{(str(row['candidate_id']), int(row['rung_index']))!r}",
            )
    return frame, {"path": _relative(path), "sha256": actual, "rows": int(len(frame))}


def _join_candidate_tags(
    candidates: pd.DataFrame,
    pivots: pd.DataFrame,
    source: str,
) -> pd.DataFrame:
    all_ids = set(candidates["candidate_id"].astype(str))
    unknown = sorted(set(pivots["candidate_id"].astype(str)) - all_ids)
    if unknown:
        raise JoinUnavailable(
            "pivot.candidate_id",
            f"{source} has {len(unknown)} pivot candidate IDs absent from candidates, "
            f"first {unknown[0]!r}",
        )
    clear = candidates[candidates["compliance_status"] == "CLEAR"].copy()
    if clear.empty:
        return clear
    invalid_phase = sorted(set(int(value) for value in clear["phase"]) - set(PHASES))
    if invalid_phase:
        raise JoinUnavailable(
            "candidates.phase",
            f"{source} CLEAR candidates have invalid phases {invalid_phase}",
        )
    invalid_side = sorted(set(int(value) for value in clear["side"]) - {-1, 1})
    if invalid_side:
        raise JoinUnavailable(
            "candidates.side",
            f"{source} CLEAR candidates have invalid sides {invalid_side}",
        )
    if (clear["rung_mask"] <= 0).any():
        row = clear.loc[clear["rung_mask"] <= 0].iloc[0]
        raise JoinUnavailable(
            "candidates.rung_mask",
            f"{source} candidate {row['candidate_id']!r} has nonpositive rung_mask "
            f"{int(row['rung_mask'])}",
        )
    lowest = (
        pivots.sort_values(["candidate_id", "rung_index"])
        .drop_duplicates("candidate_id", keep="first")
        .drop(columns=["asset", "d8"])
        .rename(columns={"side": "pivot_side"})
    )
    joined = clear.merge(
        lowest,
        on="candidate_id",
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    missing = joined["_merge"] != "both"
    if missing.any():
        candidate_id = str(joined.loc[missing, "candidate_id"].iloc[0])
        if MUTANT == "missing_tag_accepted":
            joined = joined.loc[~missing].copy()
        else:
            raise JoinUnavailable(
                "pivot.candidate_id",
                f"{source} CLEAR candidate {candidate_id!r} has no pivot tag",
            )
    joined = joined.drop(columns="_merge")
    if joined.empty:
        return joined
    expected_rung = joined["rung_mask"].map(
        lambda value: (int(value) & -int(value)).bit_length() - 1
    )
    wrong_rung = joined["rung_index"].astype(np.int64) != expected_rung.astype(np.int64)
    if wrong_rung.any():
        row = joined.loc[wrong_rung].iloc[0]
        expected = int(expected_rung.loc[wrong_rung].iloc[0])
        raise JoinUnavailable(
            "pivot.rung_index",
            f"{source} candidate {row['candidate_id']!r} lowest pivot rung "
            f"{int(row['rung_index'])} expected fired rung {expected}",
        )
    wrong_side = joined["pivot_side"].astype(np.int64) != joined["side"].astype(np.int64)
    if wrong_side.any():
        row = joined.loc[wrong_side].iloc[0]
        raise JoinUnavailable(
            "pivot.side",
            f"{source} candidate {row['candidate_id']!r} pivot side "
            f"{int(row['pivot_side'])} differs from candidate side {int(row['side'])}",
        )
    return joined


def _feature_frame(
    joined: pd.DataFrame,
    teacher: Mapping[str, tuple[str, float, int]],
    source: str,
) -> pd.DataFrame:
    if joined.empty:
        return pd.DataFrame()
    frame = joined.sort_values(
        ["phase", "decision_ts_ns", "candidate_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    leg_size = (frame["pivot_mid2"] - frame["leg_start_mid2"]).abs()
    if (leg_size == 0).any():
        row = frame.loc[leg_size == 0].iloc[0]
        raise JoinUnavailable(
            "pivot.leg_size",
            f"{source} candidate {row['candidate_id']!r} has zero pivot leg size",
        )
    if (frame["threshold_mid2_raw"] <= 0).any():
        row = frame.loc[frame["threshold_mid2_raw"] <= 0].iloc[0]
        raise JoinUnavailable(
            "pivot.threshold_mid2_raw",
            f"{source} candidate {row['candidate_id']!r} has threshold "
            f"{int(row['threshold_mid2_raw'])}",
        )
    pivot_age = frame["decision_ts_ns"] - frame["pivot_ts_recv_ns"]
    if (pivot_age < 0).any():
        row = frame.loc[pivot_age < 0].iloc[0]
        raise JoinUnavailable(
            "pivot.pivot_age_ns",
            f"{source} candidate {row['candidate_id']!r} has negative pivot age",
        )
    raw_rung_mask = frame["rung_mask"].astype(np.int64)
    frame["leg_signed"] = frame["side"] * (
        frame["pivot_mid2"] - frame["leg_start_mid2"]
    )
    frame["retrace_ratio"] = (
        (frame["pivot_mid2"] - frame["conf_mid2"]).abs() / leg_size
    )
    frame["threshold_frac"] = (
        (frame["pivot_mid2"] - frame["conf_mid2"]).abs()
        / frame["threshold_mid2_raw"]
    )
    frame["pivot_age_ns"] = pivot_age
    frame["legdur_ns"] = frame["pivot_ts_recv_ns"] - frame["leg_start_ts_recv_ns"]
    frame["events_in_leg"] = frame["pivot_ordinal"] - frame["leg_start_ordinal"]
    frame["events_since_pivot"] = (
        frame["confirmation_event_ordinal"] - frame["pivot_ordinal"]
    )
    frame["n_rungs_fired"] = raw_rung_mask.map(lambda value: int(value).bit_count())
    frame["time_rank"] = frame.groupby("phase", sort=False).cumcount()
    frame["recency"] = (
        frame["prefix_last_event_ordinal"] - frame["confirmation_event_ordinal"]
    )
    frame["rung_mask"] = raw_rung_mask.map(str)
    frame["delay"] = frame["delay"].astype(str)
    statuses: list[str | None] = []
    certs: list[float] = []
    exits: list[int | None] = []
    for candidate_id in frame["candidate_id"].astype(str):
        hit = teacher.get(candidate_id)
        if hit is None:
            statuses.append(None)
            certs.append(float("nan"))
            exits.append(None)
            continue
        status, cert, exit_ts = hit
        if status == "READY" and not np.isfinite(cert):
            raise JoinUnavailable(
                "teacher.cert_close_usd",
                f"{source} READY candidate {candidate_id!r} has non-finite cert {cert!r}",
            )
        statuses.append(status)
        certs.append(float(cert))
        exits.append(int(exit_ts))
    frame["ready"] = np.asarray([status == "READY" for status in statuses], dtype=bool)
    frame["cash_usd"] = np.asarray(
        [cert if status == "READY" else 0.0 for status, cert in zip(statuses, certs)],
        dtype=np.float64,
    )
    frame["exit_ts_ns"] = pd.Series(exits, dtype=object)
    frame["trainable"] = False
    frame["target"] = np.int8(0)
    for phase in PHASES:
        cell_indices = frame.index[frame["phase"] == phase].tolist()
        ready_indices = [index for index in cell_indices if bool(frame.at[index, "ready"])]
        if not ready_indices:
            continue
        winner = min(
            ready_indices,
            key=lambda index: (-certs[index], str(frame.at[index, "candidate_id"])),
        )
        frame.loc[cell_indices, "trainable"] = True
        frame.at[winner, "target"] = np.int8(1)
    numeric = frame.loc[:, list(NUMERIC_FEATURES)].to_numpy(dtype=np.float64)
    if numeric.shape[1] != len(NUMERIC_FEATURES) or not np.isfinite(numeric).all():
        raise JoinUnavailable(
            "features.numeric",
            f"{source} has non-finite or malformed numeric features",
        )
    if any(not value for value in frame["delay"].astype(str)):
        raise JoinUnavailable("features.delay", f"{source} has empty delay category")
    return frame


def _load_teacher(
    asset: str,
    d8: int,
    wanted: Sequence[str],
) -> tuple[Mapping[str, tuple[str, float, int]], dict[str, object]]:
    path = TEACHERS / asset / f"{d8}.tsv"
    receipt = SOURCE_RECEIPTS / asset / f"{d8}.teacher.json"
    actual, receipt_sha, expected = _verified_output(path, receipt, "teacher")
    teacher, loaded_path = _base._load_teacher(asset, d8, wanted)
    if loaded_path != path:
        raise JoinUnavailable(
            "teacher.path",
            f"teacher loader returned {loaded_path} expected {path}",
        )
    return teacher, {
        "path": _relative(path),
        "sha256": actual,
        "receipt": _relative(receipt),
        "receipt_sha256": receipt_sha,
        "output_sha256": expected,
        "matched_rows": len(teacher),
    }


def _empty_day(asset: str, d8: int, selected: bool, sources: Mapping[str, object]) -> DayBundle:
    return DayBundle(asset, d8, selected, False, pd.DataFrame(), sources)


def _load_day(
    asset: str,
    day: object,
    selected: bool,
    expected_tag_sha: str | None,
) -> DayBundle:
    if day.d8 > WINDOW_END_D8:
        raise JoinUnavailable(
            "window.2025",
            f"refusing to open {asset}/{day.d8} outside the 2022-2024 window",
        )
    candidates, candidate_source = _load_candidates(asset, day.d8)
    sources: dict[str, object] = {}
    if candidate_source:
        sources["candidates"] = candidate_source
    if candidates.empty:
        return _empty_day(asset, day.d8, selected, sources)
    if expected_tag_sha is None:
        raise JoinUnavailable(
            "stage0_receipt.tag_sha256_manifest",
            f"stage0 receipt lacks pivot hash for {asset}/{day.d8}",
        )
    pivots, pivot_source = _load_pivots(asset, day.d8, expected_tag_sha)
    sources["pivot"] = pivot_source
    joined = _join_candidate_tags(candidates, pivots, f"{asset}/{day.d8}")
    if joined.empty:
        return DayBundle(asset, day.d8, selected, True, pd.DataFrame(), sources)
    wanted = joined["candidate_id"].astype(str).tolist()
    teacher, teacher_source = _load_teacher(asset, day.d8, wanted)
    sources["teacher"] = teacher_source
    frame = _feature_frame(joined, teacher, f"{asset}/{day.d8}")
    return DayBundle(asset, day.d8, selected, True, frame, sources)


def _load_day_job(item: tuple[str, object, bool, str | None]) -> DayBundle:
    return _load_day(*item)


def _build_datasets(
    routed: Sequence[object],
    selected_flags: Sequence[bool],
    tag_hashes: Mapping[str, Mapping[int, str]],
) -> tuple[dict[str, AssetDataset], list[dict[str, object]], float]:
    jobs = [
        (asset, day, bool(selected), tag_hashes[asset].get(day.d8))
        for day, selected in zip(routed, selected_flags)
        for asset in ASSETS
    ]
    started = time.perf_counter()
    bundles: list[DayBundle] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for index, bundle in enumerate(pool.map(_load_day_job, jobs), start=1):
            bundles.append(bundle)
            if index % 250 == 0:
                print(f"loaded {index}/{len(jobs)} asset-days", flush=True)
    load_seconds = time.perf_counter() - started
    datasets: dict[str, AssetDataset] = {}
    opened: list[dict[str, object]] = []
    for asset in ASSETS:
        asset_days = sorted(
            (bundle for bundle in bundles if bundle.asset == asset),
            key=lambda bundle: bundle.d8,
        )
        by_day = {bundle.d8: bundle for bundle in asset_days}
        frames = [bundle.frame for bundle in asset_days if not bundle.frame.empty]
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not frame.empty:
            frame["d8"] = frame["d8"].astype(np.int64)
            frame["phase"] = frame["phase"].astype(np.int64)
            frame["target"] = frame["target"].astype(np.int8)
            frame["trainable"] = frame["trainable"].astype(bool)
        datasets[asset] = AssetDataset(asset, frame, by_day)
        for bundle in asset_days:
            if bundle.sources:
                opened.append(
                    {
                        "asset": bundle.asset,
                        "d8": bundle.d8,
                        "joinable": bundle.joinable,
                        **dict(bundle.sources),
                    }
                )
    return datasets, opened, load_seconds


def _training_indices(frame: pd.DataFrame, d8: int) -> np.ndarray:
    if MUTANT == "future_train_leak":
        before = frame["d8"].to_numpy(dtype=np.int64) <= d8
    else:
        before = frame["d8"].to_numpy(dtype=np.int64) < d8
    trainable = frame["trainable"].to_numpy(dtype=bool)
    indices = np.flatnonzero(before & trainable)
    if len(indices) and int(frame.iloc[indices]["d8"].max()) >= d8:
        raise JoinUnavailable(
            "fit.future_train_leak",
            f"training rows for day {d8} include d8 at or after the scored day",
        )
    return indices


def _cell_indices(frame: pd.DataFrame, d8: int) -> tuple[np.ndarray, ...]:
    day_indices = np.flatnonzero(frame["d8"].to_numpy(dtype=np.int64) == d8)
    cells: list[np.ndarray] = []
    for phase in PHASES:
        indices = day_indices[
            frame.iloc[day_indices]["phase"].to_numpy(dtype=np.int64) == phase
        ]
        if len(indices):
            cells.append(indices)
    return tuple(cells)


def _fallback_pick(frame: pd.DataFrame, indices: np.ndarray) -> int:
    return min(
        (int(index) for index in indices),
        key=lambda index: (
            int(frame.at[index, "decision_ts_ns"]),
            str(frame.at[index, "candidate_id"]),
        ),
    )


def _scored_pick(frame: pd.DataFrame, indices: np.ndarray, scores: np.ndarray) -> int:
    best = 0
    for position in range(1, len(indices)):
        score = float(scores[position])
        best_score = float(scores[best])
        index = int(indices[position])
        best_index = int(indices[best])
        better = score > best_score
        if score == best_score:
            decision = int(frame.at[index, "decision_ts_ns"])
            best_decision = int(frame.at[best_index, "decision_ts_ns"])
            better = decision > best_decision or (
                decision == best_decision
                and str(frame.at[index, "candidate_id"])
                < str(frame.at[best_index, "candidate_id"])
            )
        if better:
            best = position
    return int(indices[best])


def _entry_price_twin(frame: pd.DataFrame, indices: np.ndarray) -> int:
    return min(
        (int(index) for index in indices),
        key=lambda index: (
            -float(frame.at[index, "side"] * frame.at[index, "entry_mid2"]),
            -int(frame.at[index, "decision_ts_ns"]),
            str(frame.at[index, "candidate_id"]),
        ),
    )


def _catboost_classifier() -> object:
    _require_catboost()
    assert CatBoostClassifier is not None
    return CatBoostClassifier(
        loss_function="Logloss",
        depth=6,
        iterations=500,
        learning_rate=0.05,
        random_seed=RANDOM_SEED,
        thread_count=1,
        allow_writing_files=False,
        verbose=False,
    )


def _fit_day(dataset: AssetDataset, d8: int) -> FitResult:
    frame = dataset.frame
    cells = _cell_indices(frame, d8)
    train_indices = _training_indices(frame, d8)
    target = frame.iloc[train_indices]["target"].to_numpy(dtype=np.int8)
    positives = int(target.sum())
    train_cells = int(
        frame.iloc[train_indices][["d8", "phase"]].drop_duplicates().shape[0]
    )
    fallback = len(train_indices) == 0 or positives == 0
    started = time.perf_counter()
    chosen: list[int] = []
    twin_matches = 0
    if fallback:
        chosen = [_fallback_pick(frame, indices) for indices in cells]
    else:
        model = _catboost_classifier()
        train_x = frame.iloc[train_indices].loc[:, list(FEATURES)]
        model.fit(
            train_x,
            target,
            cat_features=list(CATEGORICAL_FEATURES),
            verbose=False,
        )
        for indices in cells:
            scores = model.predict_proba(
                frame.iloc[indices].loc[:, list(FEATURES)]
            )[:, 1]
            chosen.append(_scored_pick(frame, indices, scores))
    for picked, indices in zip(chosen, cells):
        twin_matches += int(picked == _entry_price_twin(frame, indices))
    return FitResult(
        asset=dataset.asset,
        d8=d8,
        chosen_indices=tuple(chosen),
        training_rows=int(len(train_indices)),
        training_positive_rows=positives,
        training_cells=train_cells,
        evaluation_cells=len(cells),
        fallback_no_train=fallback,
        twin_matches=twin_matches,
        twin_cells=len(cells),
        fit_seconds=time.perf_counter() - started,
    )


def _fit_job(item: tuple[AssetDataset, int]) -> FitResult:
    return _fit_day(*item)


def _evaluation_jobs(datasets: Mapping[str, AssetDataset]) -> list[tuple[AssetDataset, int]]:
    jobs: list[tuple[AssetDataset, int]] = []
    days = {asset: 0 for asset in ASSETS}
    for asset in ASSETS:
        dataset = datasets[asset]
        for d8, bundle in sorted(dataset.days.items()):
            if not bundle.selected or not bundle.joinable:
                continue
            days[asset] += 1
            jobs.append((dataset, d8))
    if days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"Stage 1 gated denominators {days} expected {EXPECTED_GATED_DAYS}",
        )
    return jobs


def _run_fits(
    jobs: Sequence[tuple[AssetDataset, int]],
) -> tuple[list[FitResult], dict[str, object], float]:
    if not jobs:
        raise JoinUnavailable("fit.jobs", "no gated joinable days to fit")
    sample_job = max(
        jobs,
        key=lambda item: len(_training_indices(item[0].frame, item[1])),
    )
    sample_started = time.perf_counter()
    sample_result = _fit_job(sample_job)
    sample_seconds = time.perf_counter() - sample_started
    projected_seconds = sample_seconds * len(jobs) / WORKERS
    projection = {
        "method": "one heaviest frozen model, retained as an evaluated model",
        "asset": sample_result.asset,
        "d8": sample_result.d8,
        "training_rows": sample_result.training_rows,
        "sample_seconds": round(sample_seconds, 6),
        "models": len(jobs),
        "workers": WORKERS,
        "projected_seconds": round(projected_seconds, 3),
        "tripwire_seconds": TRIPWIRE_SECONDS,
    }
    print(
        f"projection={projected_seconds:.1f}s from "
        f"{sample_result.asset}/{sample_result.d8} ({sample_seconds:.3f}s)",
        flush=True,
    )
    if projected_seconds > TRIPWIRE_SECONDS:
        raise JoinUnavailable(
            "fit.projection",
            f"Stage 1 projects to {projected_seconds:.1f}s, above {TRIPWIRE_SECONDS:.1f}s",
        )
    remaining = [
        item
        for item in jobs
        if not (item[0] is sample_job[0] and item[1] == sample_job[1])
    ]
    results = [sample_result]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(_fit_job, item) for item in remaining]
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 50 == 0:
                print(f"fit {index + 1}/{len(jobs)} models", flush=True)
    fit_wall = time.perf_counter() - started + sample_seconds
    return sorted(results, key=lambda result: (result.d8, result.asset)), projection, fit_wall


def _selected_entries(
    datasets: Mapping[str, AssetDataset],
    results: Sequence[FitResult],
) -> tuple[list[object], float, int]:
    entries: list[object] = []
    selected_cost = 0.0
    selected_not_ready = 0
    for result in results:
        dataset = datasets[result.asset]
        bundle = dataset.days[result.d8]
        candidate_source = bundle.sources.get("candidates")
        teacher_source = bundle.sources.get("teacher")
        if not isinstance(candidate_source, dict):
            raise JoinUnavailable(
                "sources.candidates",
                f"selected {result.asset}/{result.d8} lacks candidate source",
            )
        if result.chosen_indices and not isinstance(teacher_source, dict):
            raise JoinUnavailable(
                "sources.teacher",
                f"selected {result.asset}/{result.d8} lacks teacher source",
            )
        for index in result.chosen_indices:
            row = dataset.frame.iloc[index]
            ready = bool(row["ready"])
            exit_value = row["exit_ts_ns"]
            exit_ts = None if exit_value is None or pd.isna(exit_value) else int(exit_value)
            cost = float(row["frozen_cost_usd"])
            selected_cost += cost
            selected_not_ready += int(not ready)
            entries.append(
                SelectedName(
                    candidate_id=str(row["candidate_id"]),
                    asset=str(row["asset"]),
                    d8=int(row["d8"]),
                    phase=int(row["phase"]),
                    decision_ts_ns=int(row["decision_ts_ns"]),
                    frozen_cost_usd=cost,
                    cash_usd=float(row["cash_usd"]),
                    exit_ts_ns=exit_ts,
                    ready=ready,
                    source_candidates=str(candidate_source["path"]),
                    source_teacher=(
                        str(teacher_source["path"])
                        if isinstance(teacher_source, dict)
                        else None
                    ),
                    candidates_output_sha256=str(candidate_source["output_sha256"]),
                    teacher_output_sha256=(
                        str(teacher_source["output_sha256"])
                        if isinstance(teacher_source, dict)
                        else None
                    ),
                )
            )
    return entries, selected_cost, selected_not_ready


def _dollar_stop(line: object) -> dict[str, object]:
    blockers: list[str] = []
    if line.trades <= 0:
        blockers.append("trades == 0")
    for asset, rung in RUNGS_USD.items():
        value = float(line.usd_per_asset_day[asset])
        if value < rung:
            blockers.append(
                f"{asset} usd_per_asset_day {value} short of {rung} by {rung - value}"
            )
    if not (line.max_drawdown_usd < DRAWDOWN_LIMIT_USD):
        blockers.append(
            f"max_drawdown_usd {line.max_drawdown_usd} is not < "
            f"{DRAWDOWN_LIMIT_USD}"
        )
    if line.max_entries_portfolio_day > ENTRY_CAP:
        blockers.append(
            f"max_entries_portfolio_day {line.max_entries_portfolio_day} exceeds "
            f"{ENTRY_CAP}"
        )
    if line.overlap_violations != 0:
        blockers.append(f"overlap_violations {line.overlap_violations} != 0")
    verdict = "KILL" if blockers else "RUNGS"
    return {
        "verdict": verdict,
        "rungs_usd": dict(RUNGS_USD),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "entry_cap": ENTRY_CAP,
        "required_overlap_violations": 0,
        "required_trades_min": 1,
        "blockers": blockers,
        "shortfall_usd": dict(line.shortfall_usd),
        "verbatim": {"RUNGS": RUNGS_VERBATIM, "KILL": KILL_VERBATIM},
        "applied": RUNGS_VERBATIM if verdict == "RUNGS" else KILL_VERBATIM,
    }


def _fit_receipt(results: Sequence[FitResult]) -> dict[str, object]:
    fallback = {asset: 0 for asset in ASSETS}
    twin_matches = {asset: 0 for asset in ASSETS}
    twin_cells = {asset: 0 for asset in ASSETS}
    per_day = {asset: [] for asset in ASSETS}
    for result in results:
        fallback[result.asset] += int(result.fallback_no_train)
        twin_matches[result.asset] += result.twin_matches
        twin_cells[result.asset] += result.twin_cells
        per_day[result.asset].append(
            {
                "d8": result.d8,
                "training_rows": result.training_rows,
                "training_positive_rows": result.training_positive_rows,
                "training_cells": result.training_cells,
                "evaluation_cells": result.evaluation_cells,
                "fallback_no_train": result.fallback_no_train,
                "fit_seconds": round(result.fit_seconds, 6),
            }
        )
    total_matches = sum(twin_matches.values())
    total_cells = sum(twin_cells.values())
    return {
        "models": len(results),
        "fallback_no_train": {
            "total": sum(fallback.values()),
            "per_asset": fallback,
        },
        "training_rows_per_day": per_day,
        "entry_price_twin_control": {
            "definition": (
                "argmax side times entry_mid2, then maximum decision_ts_ns, "
                "then smallest candidate_id"
            ),
            "gates_verdict": False,
            "matches": total_matches,
            "cells": total_cells,
            "match_rate": total_matches / total_cells if total_cells else 0.0,
            "per_asset": {
                asset: {
                    "matches": twin_matches[asset],
                    "cells": twin_cells[asset],
                    "match_rate": (
                        twin_matches[asset] / twin_cells[asset]
                        if twin_cells[asset]
                        else 0.0
                    ),
                }
                for asset in ASSETS
            },
        },
    }


def _build_receipt(verification: Mapping[str, object]) -> dict[str, object]:
    _assert_feature_contract()
    _require_catboost()
    started = time.perf_counter()
    tag_hashes, stage0_source = _stage0_inputs()
    forecast_rows, window_days, n_forecast_rows = _base.load_window_forecast_rows(FORECAST)
    routed, _empty = _base.route_catboost_daily(forecast_rows)
    refused = _base.refused_days_without_daily(window_days, [day.day for day in routed])
    selected_flags = _base.select_expanding_median(routed)
    if any(day.d8 < WINDOW_START_D8 or day.d8 > WINDOW_END_D8 for day in routed):
        raise JoinUnavailable(
            "forecast.window",
            "routed forecast days escape 2022-03-09 through 2024-12-31",
        )
    datasets, opened, load_seconds = _build_datasets(routed, selected_flags, tag_hashes)
    jobs = _evaluation_jobs(datasets)
    results, projection, fit_seconds = _run_fits(jobs)
    entries, selected_cost, selected_not_ready = _selected_entries(datasets, results)
    line = _ceiling.summarize_line(entries, EXPECTED_GATED_DAYS)
    stop = _dollar_stop(line)
    fit = _fit_receipt(results)
    line_payload = line.as_dict()
    line_payload.update(
        {
            "selected_not_ready": selected_not_ready,
            "selected_frozen_cost_usd_total": selected_cost,
            "one_contract": True,
            "dollars_per_trade": True,
            "entry_price_twin_match_rate": fit["entry_price_twin_control"][
                "match_rate"
            ],
        }
    )
    selected_days = sum(bool(flag) for flag in selected_flags)
    opened_days = [int(row["d8"]) for row in opened]
    if opened_days and max(opened_days) > WINDOW_END_D8:
        raise JoinUnavailable(
            "sources.2025",
            f"opened source day {max(opened_days)} after 2024-12-31",
        )
    wall_seconds = time.perf_counter() - started
    return {
        "schema": SCHEMA,
        "status": stop["verdict"],
        "verdict": stop["verdict"],
        "label": (
            "frozen per-asset causal CatBoost fitted name read at age 180. "
            "Teacher-cash can kill and cannot promote."
        ),
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "check_command": CHECK,
        "peek_note": PEEK_NOTE,
        "candidate_columns": list(CANDIDATE_COLUMNS),
        "pivot_columns": list(PIVOT_COLUMNS),
        "teacher_columns": list(TEACHER_COLUMNS),
        "features": {
            "numeric": list(NUMERIC_FEATURES),
            "categorical_native": list(CATEGORICAL_FEATURES),
        },
        "target": (
            "is_cell_best, the maximum READY cert_close_usd candidate in the "
            "cell, tie-break smallest candidate_id; cells with no READY row drop"
        ),
        "training_gate_states": "both",
        "evaluation_gate": "frozen expanding-median selected days",
        "tie_break": ["maximum score", "maximum decision_ts_ns", "smallest candidate_id"],
        "fallback": (
            "A day with an empty or positive-free training set uses earliest "
            "CLEAR in every cell and increments fallback_no_train."
        ),
        "learner": {
            "name": "CatBoostClassifier",
            "version": CATBOOST_VERSION,
            "loss_function": "Logloss",
            "depth": 6,
            "iterations": 500,
            "learning_rate": 0.05,
            "random_seed": RANDOM_SEED,
            "early_stopping": False,
            "class_weights": None,
            "tuning": False,
            "cross_validation": False,
            "per_asset_models": True,
            "thread_count_per_model": 1,
        },
        "fit": fit,
        "lines": {"fitted": line_payload},
        "dollar_stop": stop,
        "day_counts": {
            "routed": len(routed),
            "selected_gate_days": selected_days,
            "refused_no_forecast": len(refused),
            "locked_gated_denominators": dict(EXPECTED_GATED_DAYS),
        },
        "projection": projection,
        "verification": dict(verification),
        "workers": WORKERS,
        "timing_seconds": {
            "load": round(load_seconds, 3),
            "fit": round(fit_seconds, 3),
            "wall": round(wall_seconds, 3),
        },
        "forbidden_reads": {
            "teacher_fields_unparsed": list(_base.PEEK_COLS),
            "max_candidate_d8_opened": max(opened_days) if opened_days else None,
            "max_teacher_d8_opened": max(
                (
                    int(row["d8"])
                    for row in opened
                    if isinstance(row.get("teacher"), dict)
                ),
                default=None,
            ),
            "max_pivot_d8_opened": max(
                (
                    int(row["d8"])
                    for row in opened
                    if isinstance(row.get("pivot"), dict)
                ),
                default=None,
            ),
            "opened_2025_candidate_teacher_or_pivot_files": 0,
            "pivot_lines_scored": False,
        },
        "tag_can_promote": False,
        "teacher_cash_can_promote": False,
        "one_read": True,
        "tickets_started": [],
        "units_started": ["C_STAGE1"],
        "sources": {
            "script": _source_file(Path(__file__).resolve()),
            "covering_brief": _source_file(COVERING_BRIEF),
            "stage0_receipt": stage0_source,
            "stage0_judge": _source_file(STAGE0_JUDGE),
            "freeze": _source_file(FREEZE),
            "forecast": _source_file(FORECAST),
            "templates": {
                "pivot_join_and_dollar_block": _source_file(
                    REPO / ".audit/score_threshold_pivot_name_rules.py"
                ),
                "loaders_gate_denominators": _source_file(
                    REPO / ".audit/score_threshold_rank_live.py"
                ),
                "selftest_receipt": _source_file(REPO / ".audit/score_h5_top2.py"),
            },
            "candidates_root": _relative(CANDIDATES),
            "teacher_root": _relative(TEACHERS),
            "pivot_root": _relative(PIVOT_ROOT),
            "receipts_root": _relative(SOURCE_RECEIPTS),
            "opened_artifacts": opened,
        },
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _synthetic_candidates(d8: int) -> pd.DataFrame:
    rows = []
    for candidate_id, decision, side, rung_mask, delay, entry_mid2 in (
        ("early", 10, 1, 1, "FAST_OPEN_15", 100),
        ("winner", 20, -1, 3, "STANDARD_120", 90),
        ("late", 30, 1, 2, "STANDARD_120", 110),
    ):
        rows.append(
            {
                "candidate_id": candidate_id,
                "asset": "HG",
                "d8": d8,
                "confirmation_event_ordinal": 30,
                "decision_ts_ns": decision,
                "side": side,
                "phase": 0,
                "rung_mask": rung_mask,
                "delay": delay,
                "prefix_last_event_ordinal": 35,
                "entry_mid2": entry_mid2,
                "entry_spread_usd": 1.0,
                "frozen_cost_usd": 2.0,
                "atr14_prev_usd": 3.0,
                "spread_prior_present": 1,
                "spread_prior_usd": 4.0,
                "sane_ceiling_usd": 5.0,
                "compliance_status": "CLEAR",
                "compliance_distance_sec": 6.0,
            }
        )
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)


def _synthetic_pivots(d8: int) -> pd.DataFrame:
    rows = []
    for candidate_id, side, rung_indices in (
        ("early", 1, (0,)),
        ("winner", -1, (0, 1)),
        ("late", 1, (1,)),
    ):
        for rung_index in rung_indices:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "asset": "HG",
                    "d8": d8,
                    "rung_index": rung_index,
                    "side": side,
                    "pivot_mid2": 100,
                    "pivot_ts_recv_ns": 5,
                    "pivot_ordinal": 20,
                    "leg_start_mid2": 80,
                    "leg_start_ts_recv_ns": 1,
                    "leg_start_ordinal": 10,
                    "conf_mid2": 90,
                    "threshold_mid2_raw": 10,
                }
            )
    return pd.DataFrame(rows, columns=PIVOT_COLUMNS)


def _selftest_guard() -> None:
    with tempfile.TemporaryDirectory(prefix="threshold-cfit-selftest-") as directory:
        path = Path(directory) / "stored.tsv"
        path.write_text("candidate_id\noriginal\n")
        expected = _sha256_file(path)
        path.write_text("candidate_id\ncorrupted\n")
        try:
            _verify_file_sha(path, expected, "selftest.candidate_id")
        except JoinUnavailable:
            return
        raise AssertionError("selftest accepted a corrupted synthetic candidate_id")


def _selftest() -> int:
    if MUTANT and MUTANT not in KNOWN_MUTANTS:
        raise ValueError(f"unknown QRE2_CFIT_MUTANT {MUTANT!r}")
    _assert_feature_contract()
    _require_catboost()
    _selftest_guard()
    candidates = _synthetic_candidates(20220310)
    pivots = _synthetic_pivots(20220310)
    joined = _join_candidate_tags(candidates, pivots, "synthetic/20220310")
    missing = pivots[pivots["candidate_id"] != "late"]
    try:
        _join_candidate_tags(candidates, missing, "synthetic/missing")
    except JoinUnavailable:
        pass
    else:
        raise AssertionError("selftest accepted a CLEAR candidate with no pivot tag")
    teacher = {
        "early": ("READY", 1.0, 11),
        "winner": ("READY", 90.0, 21),
        "late": ("READY", 3.0, 31),
    }
    day1 = _feature_frame(joined, teacher, "synthetic/20220310")
    if day1.loc[day1["target"] == 1, "candidate_id"].tolist() != ["winner"]:
        raise AssertionError("selftest cell-best target changed")
    early = _fallback_pick(day1, day1.index.to_numpy(dtype=np.int64))
    if str(day1.at[early, "candidate_id"]) != "early":
        raise AssertionError("selftest fallback is not earliest CLEAR")
    tied = _scored_pick(
        day1,
        day1.index.to_numpy(dtype=np.int64),
        np.zeros(len(day1), dtype=np.float64),
    )
    if str(day1.at[tied, "candidate_id"]) != "late":
        raise AssertionError("selftest fitted tie-break is not latest decision")
    day2 = _feature_frame(
        _join_candidate_tags(
            _synthetic_candidates(20220311),
            _synthetic_pivots(20220311),
            "synthetic/20220311",
        ),
        teacher,
        "synthetic/20220311",
    )
    frame = pd.concat([day1, day2], ignore_index=True)
    dataset = AssetDataset(
        "HG",
        frame,
        {
            20220310: DayBundle("HG", 20220310, True, True, day1, {}),
            20220311: DayBundle("HG", 20220311, True, True, day2, {}),
        },
    )
    prior = _training_indices(frame, 20220311)
    if len(prior) != len(day1) or int(frame.iloc[prior]["d8"].max()) >= 20220311:
        raise AssertionError("selftest future training row accepted")
    result = _fit_day(dataset, 20220311)
    if result.training_rows != len(day1) or result.training_positive_rows != 1:
        raise AssertionError(f"selftest training counts changed: {result}")
    if result.evaluation_cells != 1 or len(result.chosen_indices) != 1:
        raise AssertionError(f"selftest evaluation shape changed: {result}")
    print("selftest_ok")
    return 0


def _verification_command(mutant: str | None = None) -> str:
    if mutant is None:
        return f"{CHECK} --selftest"
    return f"QRE2_CFIT_MUTANT={mutant} {CHECK} --selftest"


def _run_red_first_checks() -> dict[str, object]:
    checks: list[tuple[str, str | None]] = [("selftest", None)]
    checks.extend((name, name) for name in MUTANTS)
    checks.append(("guard_mutant", GUARD_MUTANT))
    results: dict[str, object] = {}
    for label, mutant in checks:
        env = dict(os.environ)
        env.pop("QRE2_CFIT_MUTANT", None)
        if mutant is not None:
            env["QRE2_CFIT_MUTANT"] = mutant
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--selftest"],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        expected_red = mutant is not None
        if expected_red and completed.returncode == 0:
            raise JoinUnavailable(
                "verification.mutant",
                f"mutant {mutant!r} stayed green",
            )
        if not expected_red and completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip().splitlines()[-1:]
            raise JoinUnavailable(
                "verification.selftest",
                f"baseline selftest failed with {completed.returncode}: {tail}",
            )
        results[label] = {
            "command": _verification_command(mutant),
            "exit_code": completed.returncode,
            "status": "KILLED" if expected_red else "PASS",
        }
    return {
        "red_first_before_era_read": True,
        "checks": results,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args == ["--selftest"]:
        return _selftest()
    if args:
        raise ValueError(f"unsupported arguments {args}")
    if MUTANT:
        raise ValueError("QRE2_CFIT_MUTANT is allowed only with --selftest")
    verification = _run_red_first_checks()
    receipt = _build_receipt(verification)
    _write_receipt(receipt)
    line = receipt["lines"]["fitted"]
    print(
        f"receipt={_relative(RECEIPT)} verdict={receipt['verdict']} "
        f"usd_per_asset_day={line['usd_per_asset_day']} "
        f"max_drawdown_usd={line['max_drawdown_usd']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
