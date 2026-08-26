#!/usr/bin/env python3
"""Replay E1R THRESHOLD RAW with a kept FROZEN_Q3_E8 action refit.

Uses evaluate_policy_block. Writes under artifacts/cache/threshold_refit/.
Does not touch the frozen E1R_raw_THRESHOLD tree.
H3 is the default. --h5-official-e1r selects the H5 action receipt and new traces.
--h7-official-enter selects the H7 receipt and its own trace namespace.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, replace
from functools import partial
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.entry_v2 import common as C
from engine.entry_v2 import tabular_evaluation_io as evaluation_io
from engine.entry_v2.confirmation_experiment import (
    AuthoritativeConfirmationSessionSpec,
    discover_authoritative_session_specs,
)
from engine.entry_v2.tabular_campaign import (
    CachedRecoverySession,
    CachedTeacherDay,
    DENSE_FEATURE_CACHE_SCHEMA,
    OUTCOME_CACHE_SCHEMA,
    ROLLOUT_TEACHER_CACHE_SCHEMA,
    _read_manifest,
)
from engine.entry_v2.tabular_delayed_corpus import CausalFeatureShard
from engine.entry_v2.tabular_evaluation_policy import evaluate_policy_block
from engine.entry_v2.tabular_experiment import (
    EXPERIMENT_SCHEMA,
    FittedFold,
    SeedModelRoster,
)
from engine.entry_v2.tabular_fit_only import _chronology_from_mapping
from engine.entry_v2.tabular_live_replay import load_policy_day_trace
from engine.entry_v2.tabular_orchestration import _schema_from_mapping
from engine.entry_v2.tabular_recovery_contracts import RecoveryConfig

SOURCE = REPO / "artifacts/cache/port/entry_v2"
REHEARSAL = REPO / "artifacts/entry_v2/tabular_recovery/rehearsal"
FIT_EXECUTION = REHEARSAL / "fit_only/e1r/fit_only_execution.json"
ROUND2 = REHEARSAL / "fit_only/e1r/curriculum/fits/round_2"
TWO_ROUND = REHEARSAL / "fit_only/e1r/curriculum/two_round_curriculum.json"
COMPONENT_ROSTER = ROUND2 / "component_real_roster.json"
ACTION_ROSTER = ROUND2 / "action_real_roster.json"
H3_RECEIPT = REPO / ".audit/threshold-refit-h3-enter-balance.json"
H5_RECEIPT = REPO / ".audit/threshold-refit-h5-official-e1r.json"
H6_RECEIPT = REPO / ".audit/threshold-refit-h6-pairwise-enter.json"
H7_RECEIPT = REPO / ".audit/threshold-refit-h7-official-enter.json"
OUT_ROOT = REPO / "artifacts/cache/threshold_refit/replay"
H3_REPLAY_RECEIPT = REPO / ".audit/threshold-refit-h3-replay.json"
H5_REPLAY_RECEIPT = REPO / ".audit/threshold-refit-h5-replay.json"
H6_REPLAY_RECEIPT = REPO / ".audit/threshold-refit-h6-replay.json"
H7_REPLAY_RECEIPT = REPO / ".audit/threshold-refit-h7-replay.json"
DENSE_STORE = REPO / "artifacts/entry_v2/tabular_recovery/dense_store"
# The kept curriculum's teacher lineage was built from this outcome cache.
OUTCOME_CACHE_IDENTITY = "6f421af32b02ff145d3b1147590f1f2112261b307d0f54f391240f1cdf5cb72f"
OUTCOME_CACHE = REHEARSAL / "cache/outcome_sessions" / OUTCOME_CACHE_IDENTITY
SEED = 20260820
CHECK = "python3 .audit/replay_threshold_h3.py"
RUNGS = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
MAX_DRAWDOWN_USD = 1000.0
MAX_ENTRIES = 12


def _one_roster(path: Path, seed: int) -> SeedModelRoster:
    payload = json.loads(path.read_text())
    raw = next(row for row in payload["rosters"] if int(row["seed"]) == seed)
    folds = []
    for raw_fold in raw["folds"]:
        fold = dict(raw_fold)
        fold["score_range"] = tuple(fold["score_range"])
        fitted = FittedFold(**fold)
        fitted.__post_init__()
        folds.append(fitted)
    row = dict(raw)
    row["folds"] = tuple(folds)
    roster = SeedModelRoster(**row)
    roster.__post_init__()
    return roster


def swap_frozen_fold(
    roster: SeedModelRoster, bundle_dir: Path, receipt: str, objective: str
) -> SeedModelRoster:
    folds = []
    for fold in roster.folds:
        if fold.name == "FROZEN_Q3_E8":
            fold = replace(
                fold,
                bundle_path=str(bundle_dir.resolve()),
                bundle_receipt_sha256=receipt,
            )
            fold.__post_init__()
        folds.append(fold)
    folds_t = tuple(folds)
    core = {
        "schema": EXPERIMENT_SCHEMA,
        "kind": roster.kind,
        "learner_backend": roster.learner_backend,
        "seed": roster.seed,
        "shuffled_labels": roster.shuffled_labels,
        "shuffle_seed": roster.shuffle_seed,
        "folds": tuple(asdict(row) for row in folds_t),
        "chronology": roster.chronology_receipt_sha256,
        "objective": objective,
        "component_predictions": roster.component_prediction_receipt_sha256,
    }
    swapped = SeedModelRoster(
        kind=roster.kind,
        learner_backend=roster.learner_backend,
        seed=roster.seed,
        shuffled_labels=roster.shuffled_labels,
        shuffle_seed=roster.shuffle_seed,
        folds=folds_t,
        chronology_receipt_sha256=roster.chronology_receipt_sha256,
        objective=objective,
        component_prediction_receipt_sha256=(
            roster.component_prediction_receipt_sha256
        ),
        receipt_sha256=C.object_sha256(core),
    )
    swapped.__post_init__()
    return swapped


def _rungs(
    usd_per_asset_day: dict[str, float],
    trades: int,
    max_drawdown_usd: float,
    max_entries: int,
) -> bool:
    if trades <= 0 or max_drawdown_usd >= MAX_DRAWDOWN_USD:
        return False
    if max_entries > MAX_ENTRIES:
        return False
    return all(
        float(usd_per_asset_day.get(asset, 0.0)) >= floor
        for asset, floor in RUNGS.items()
    )


def load_rehearsal_outcomes(
    specs: Sequence[AuthoritativeConfirmationSessionSpec],
) -> tuple[CachedRecoverySession, ...]:
    outcomes = []
    for spec in specs:
        manifest_path = OUTCOME_CACHE / spec.asset / f"{spec.trading_day}.json"
        value = _read_manifest(manifest_path, OUTCOME_CACHE_SCHEMA)
        source = value.get("source")
        if (
            value.get("identity_sha256") != OUTCOME_CACHE_IDENTITY
            or value.get("max_delay_sec") != 300
            or not isinstance(source, dict)
            or source.get("asset") != spec.asset
            or source.get("trading_day") != spec.trading_day
        ):
            raise ValueError(f"rehearsal outcome cache differs: {manifest_path}")
        artifact = value.get("artifact_path")
        if artifact is not None and not Path(str(artifact)).is_file():
            raise FileNotFoundError(f"rehearsal outcome artifact missing: {artifact}")
        outcomes.append(
            CachedRecoverySession(
                session=spec.session,
                status=str(value["status"]),
                manifest_path=str(manifest_path),
                artifact_path=str(artifact) if artifact is not None else None,
                representation_sha256=(
                    str(value["representation_sha256"])
                    if value.get("representation_sha256") is not None
                    else None
                ),
                candidate_rows=int(value["candidate_rows"]),
                learnable_rows=int(value["learnable_rows"]),
                receipt_sha256=str(value["receipt_sha256"]),
            )
        )
    return tuple(sorted(outcomes, key=lambda row: row.session))


def dense_representations_by_day(
    teachers: Sequence[CachedTeacherDay],
    bounds: tuple[int, int],
) -> dict[int, frozenset[str]]:
    lo, hi = bounds
    representations = {}
    for teacher in teachers:
        if not lo <= teacher.trading_day <= hi:
            continue
        manifest_path = Path(teacher.artifact_path).with_suffix(".json")
        value = _read_manifest(manifest_path, ROLLOUT_TEACHER_CACHE_SCHEMA)
        rollout = value.get("rollout")
        if not isinstance(rollout, dict):
            raise ValueError(f"rollout teacher cache differs: {manifest_path}")
        receipts = frozenset(map(str, rollout.get("source_feature_receipts", ())))
        if not receipts or len(receipts) > len(C.ASSETS):
            raise ValueError(f"rollout dense roster differs: {manifest_path}")
        representations[teacher.trading_day] = receipts
    return representations


def load_rehearsal_dense_session(
    expected_by_day: Mapping[int, frozenset[str]],
    spec: AuthoritativeConfirmationSessionSpec,
    *,
    max_delay_sec: int,
) -> CausalFeatureShard:
    if max_delay_sec != 300 or spec.trading_day not in expected_by_day:
        raise ValueError(
            f"rehearsal dense request differs: {spec.asset}-{spec.trading_day}"
        )
    matches = []
    for manifest_path in DENSE_STORE.glob(
        f"*/{spec.asset}/{spec.trading_day}.json"
    ):
        value = _read_manifest(manifest_path, DENSE_FEATURE_CACHE_SCHEMA)
        if value.get("representation_sha256") in expected_by_day[spec.trading_day]:
            matches.append((manifest_path, value))
    if len(matches) != 1:
        raise ValueError(
            f"rehearsal dense cache matches {len(matches)}: "
            f"{spec.asset}-{spec.trading_day}"
        )
    manifest_path, value = matches[0]
    if value.get("identity_sha256") != manifest_path.parents[1].name:
        raise ValueError(f"rehearsal dense identity differs: {manifest_path}")
    artifact_path = Path(str(value["artifact_path"]))
    shard = CausalFeatureShard.load(artifact_path)
    if (
        shard.representation_sha256 != value.get("representation_sha256")
        or C.file_sha256(artifact_path) != value.get("artifact_sha256")
    ):
        raise ValueError(f"rehearsal dense artifact differs: {artifact_path}")
    print(f"dense cache loaded: {spec.asset}-{spec.trading_day}", flush=True)
    return shard


def main() -> int:
    h5_official_e1r = "--h5-official-e1r" in sys.argv[1:]
    h6_pairwise_enter = "--h6-pairwise-enter" in sys.argv[1:]
    h7_official_enter = "--h7-official-enter" in sys.argv[1:]
    selected_flags = tuple(
        name
        for name, enabled in (
            ("--h5-official-e1r", h5_official_e1r),
            ("--h6-pairwise-enter", h6_pairwise_enter),
            ("--h7-official-enter", h7_official_enter),
        )
        if enabled
    )
    if len(selected_flags) > 1:
        raise ValueError(
            f"replay variant flags must be mutually exclusive, got {selected_flags}"
        )
    if h7_official_enter:
        head_receipt_path = H7_RECEIPT
        replay_receipt_path = H7_REPLAY_RECEIPT
        run_name = "H7_raw_THRESHOLD"
        hypothesis = "H7_MultiClass_official_E1R_enter_balance_THRESHOLD_RAW"
        receipt_schema = "QRE2THRESHOLDREFITH7REPLAY1"
        check = (
            f"ENTRY_V2_DENSE_STORE={DENSE_STORE.relative_to(REPO)} "
            f"ENTRY_V2_PREDICT_THREADS=16 {CHECK} --h7-official-enter"
        )
    elif h6_pairwise_enter:
        head_receipt_path = H6_RECEIPT
        replay_receipt_path = H6_REPLAY_RECEIPT
        run_name = "H6_raw_THRESHOLD"
        hypothesis = "H6_PairLogitPairwise_enter_balance_THRESHOLD_RAW"
        receipt_schema = "QRE2THRESHOLDREFITH6REPLAY1"
        check = f"ENTRY_V2_PREDICT_THREADS=16 {CHECK} --h6-pairwise-enter"
    elif h5_official_e1r:
        head_receipt_path = H5_RECEIPT
        replay_receipt_path = H5_REPLAY_RECEIPT
        run_name = "H5_raw_THRESHOLD"
        hypothesis = "H5_MultiClass_unweighted_official_E1R_THRESHOLD_RAW"
        receipt_schema = "QRE2THRESHOLDREFITH5REPLAY1"
        check = f"{CHECK} --h5-official-e1r"
    else:
        head_receipt_path = H3_RECEIPT
        replay_receipt_path = H3_REPLAY_RECEIPT
        run_name = "H3_raw_THRESHOLD"
        hypothesis = "H3_MultiClass_enter_balance_THRESHOLD_RAW"
        receipt_schema = "QRE2THRESHOLDREFITH3REPLAY1"
        check = CHECK
    if "--selftest" in sys.argv[1:]:
        head = json.loads(head_receipt_path.read_text())
        roster = _one_roster(ACTION_ROSTER, SEED)
        swapped = swap_frozen_fold(
            roster,
            REPO / head["bundle"],
            str(head["bundle_receipt_sha256"]),
            str(head["objective"]),
        )
        fold = swapped.bundle_for_day(20210721)
        if fold.name != "FROZEN_Q3_E8":
            raise AssertionError(f"THRESHOLD day fold {fold.name}")
        if fold.bundle_receipt_sha256 != head["bundle_receipt_sha256"]:
            raise AssertionError("swapped fold receipt differs")
        if swapped.objective != head["objective"]:
            raise AssertionError(f"swapped objective {swapped.objective}")
        if h6_pairwise_enter and run_name != "H6_raw_THRESHOLD":
            raise AssertionError(f"H6 trace namespace {run_name}")
        if h7_official_enter and run_name != "H7_raw_THRESHOLD":
            raise AssertionError(f"H7 trace namespace {run_name}")
        print("selftest_ok")
        return 0
    print(f"phase 1/5: load {hypothesis} and rehearsal metadata", flush=True)
    head = json.loads(head_receipt_path.read_text())
    if not head.get("healthy_on_validation"):
        raise ValueError(f"action receipt is not healthy: {head_receipt_path}")
    if h5_official_e1r and not head.get("official_e1r"):
        raise ValueError(f"H5 receipt does not use official E1R: {head_receipt_path}")
    if h6_pairwise_enter and (
        head.get("objective") != "PairLogitPairwise"
        or not head.get("enter_balance")
        or head.get("official_e1r")
        or head.get("enter_scale_override") is not None
    ):
        raise ValueError(f"H6 action receipt differs: {head_receipt_path}")
    if h7_official_enter and (
        head.get("objective") != "MultiClass"
        or not head.get("enter_balance")
        or not head.get("official_e1r")
        or head.get("enter_scale_override") is not None
    ):
        raise ValueError(f"H7 action receipt differs: {head_receipt_path}")
    execution = json.loads(FIT_EXECUTION.read_text())
    chronology = _chronology_from_mapping(execution["chronology"])
    round2 = json.loads((ROUND2 / "curriculum_round.json").read_text())
    schema = _schema_from_mapping(round2["feature_schema"])
    two = json.loads(TWO_ROUND.read_text())
    teachers = tuple(CachedTeacherDay(**row) for row in two["final_teachers"])
    component = _one_roster(COMPONENT_ROSTER, SEED)
    action = swap_frozen_fold(
        _one_roster(ACTION_ROSTER, SEED),
        REPO / head["bundle"],
        str(head["bundle_receipt_sha256"]),
        str(head["objective"]),
    )
    os.environ["ENTRY_V2_DENSE_STORE"] = str(DENSE_STORE)
    print("phase 1/5 complete", flush=True)
    print("phase 2/5: discover THRESHOLD sessions", flush=True)
    specs = discover_authoritative_session_specs(SOURCE, chronology.threshold)
    print(f"phase 2/5 complete: {len(specs)} sessions", flush=True)
    print("phase 3/5: load rehearsal outcome cache", flush=True)
    outcomes = load_rehearsal_outcomes(specs)
    expected_dense = dense_representations_by_day(teachers, chronology.threshold)
    evaluation_io.load_or_materialize_dense_session = partial(
        load_rehearsal_dense_session,
        expected_dense,
    )
    print(f"phase 3/5 complete: {len(outcomes)} outcomes", flush=True)
    print("phase 4/5: evaluate_policy_block THRESHOLD RAW", flush=True)
    block = evaluate_policy_block(
        name=run_name,
        bounds=chronology.threshold,
        lane="real",
        component_roster=component,
        action_roster=action,
        outcomes=outcomes,
        teachers=teachers,
        specs=specs,
        feature_schema=schema,
        config=RecoveryConfig(),
        output_root=OUT_ROOT,
        mode="RAW",
    )
    print("phase 4/5 complete", flush=True)
    print("phase 5/5: score rungs and write receipt", flush=True)
    evaluation = block.evidence.evaluation
    usd = {
        row.asset: float(row.usd_per_asset_day)
        for row in evaluation.by_asset
    }
    entries = [
        len(load_policy_day_trace(path).selected_opportunity_ids)
        for path in block.trace_paths
    ]
    max_entries = max(entries) if entries else 0
    trades = int(evaluation.trades)
    drawdown = float(evaluation.max_drawdown_usd)
    payload: dict[str, Any] = {
        "schema": receipt_schema,
        "hypothesis": hypothesis,
        "seed": SEED,
        "block": str(Path(block.manifest_path).relative_to(REPO)),
        "block_receipt_sha256": block.receipt_sha256,
        "action_roster_receipt_sha256": block.action_roster_receipt_sha256,
        "trades": trades,
        "total_pnl_usd": float(evaluation.total_pnl_usd),
        "usd_per_asset_day": usd,
        "max_drawdown_usd": drawdown,
        "max_entries_portfolio_day": max_entries,
        "entries_by_day": entries,
        "clears_rungs": _rungs(usd, trades, drawdown, max_entries),
        "gate_target_pass": bool(block.gate.target_pass),
        "check_command": check,
    }
    replay_receipt_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print("phase 5/5 complete", flush=True)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
