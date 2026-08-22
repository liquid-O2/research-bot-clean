#!/usr/bin/env python3
"""A1 out-of-sample margin-rule replay (design/A1_MARGIN_RULE_SPEC.md item 3).

Diagnosis only.  Nothing here changes a chain default: the published E1R
round-2 bundles, calibration and denominators are strict-loaded by receipt and
replayed under ``policy_mode="MARGIN"``, which exists nowhere in the chain's
own call graph.

Run one (lane, seed):
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 10 \
    /usr/bin/python3 tools/diag_margin_rule_replay.py --lane real --seed 20260820
Guards first (D-017):
  python3 tools/diag_margin_rule_replay.py --selftest
  python3 tools/diag_margin_rule_replay.py --argmin-guard
Summary over the published per-seed receipts:
  python3 tools/diag_margin_rule_replay.py --summary
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable, Iterable, Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from engine.entry_v2.native_thread_cap import cap_native_thread_env  # noqa:E402
from engine.entry_v2.pod_local_lock import pod_local_flock  # noqa:E402

cap_native_thread_env()
os.environ.setdefault("ENTRY_V2_PREDICT_THREADS", "1")
os.environ.setdefault("ENTRY_V2_DENSE_STORE", str(
    REPO_ROOT / "artifacts/entry_v2/tabular_recovery/dense_store"))

import numpy as np  # noqa:E402

from engine.entry_v2 import common as C  # noqa:E402
from engine.entry_v2.confirmation_experiment import (  # noqa:E402
    discover_authoritative_session_specs,
)
from engine.entry_v2.exact_delayed_teacher import DayOptionUniverse  # noqa:E402
from engine.entry_v2.tabular_calibration import (  # noqa:E402
    AdmissionContract, evaluate_economic_gate,
    select_threshold_from_calibration_bank,
)
from engine.entry_v2.tabular_campaign import (  # noqa:E402
    load_or_materialize_dense_session, materialize_outcome_corpus,
)
from engine.entry_v2.tabular_delayed_corpus import DelayedOutcomeShard  # noqa:E402
# WHY the private imports: `_outcomes_by_day`/`_specs_by_day` define the exact
# row ordering the published DayOptionUniverse receipts were built from, and
# `_sessions_from_payload` the denominator decoding.  A local copy would fork
# silently the first time either side changed.
from engine.entry_v2.tabular_evaluation import (  # noqa:E402
    BLOCK_RESULT_SCHEMA, THRESHOLD_STORE_SCHEMA, _array_sha256,
    _outcomes_by_day, _sessions_from_payload, _specs_by_day,
    load_calibration_bundle, load_threshold_bank,
)
from engine.entry_v2.tabular_experiment import (  # noqa:E402
    ActionPredictionTable, load_seed_rosters,
)
from engine.entry_v2.tabular_live_replay import (  # noqa:E402
    load_policy_day_trace, replay_policy_block, replay_policy_day,
    save_policy_day_trace,
)
from engine.entry_v2.tabular_model_io import (  # noqa:E402
    load_action_model, load_component_model,
)
from engine.entry_v2.tabular_recovery_contracts import (  # noqa:E402
    RecoveryChronology, RecoveryConfig, RecoveryRefusal,
)
from engine.entry_v2.tabular_walk_twin import (  # noqa:E402
    replay_policy_day_multistate,
)


A1_SEED_SCHEMA = "QRE2A1MARGINSEED1"
A1_SUMMARY_SCHEMA = "QRE2A1MARGINSUMMARY1"
A1_QUANTILES = 21
# Preregistered reading ladder (spec Preregistration, user 2026-08-22).  It is
# reported, never encoded as a gate: theta is picked by the existing law.
A1_GOAL_LADDER_USD = (2_000.0, 1_500.0)

E1R_ROOT = REPO_ROOT / "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r"
DIAG_ROOT = E1R_ROOT / "diagnosis/margin_rule"
SOURCE_ROOT = REPO_ROOT / "artifacts/cache/port/entry_v2"
CACHE_ROOT = REPO_ROOT / "artifacts/entry_v2/tabular_recovery/rehearsal/cache"
REHEARSAL_BOUNDS = (20210531, 20210930)


def _strict_payload(path: Path, schema: str) -> Mapping[str, object]:
    C.guard_payload(path)
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryRefusal(f"cannot strict-load A1 input: {path}") from exc
    core = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if (value.get("schema") != schema
            or C.object_sha256(core) != value.get("receipt_sha256")):
        raise RecoveryRefusal(f"A1 input identity differs: {path}")
    return value


def _publish(path: Path, core: Mapping[str, object]) -> str:
    receipt = C.object_sha256(core)
    C.atomic_json(C.assert_workspace_output(path), {**core,
                                                    "receipt_sha256": receipt})
    return receipt


# --------------------------------------------------------------------------
# Block denominators: read from the artifacts the E1R evaluation published so
# the A1 numbers sit on byte-identical sessions and ceilings.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MarginBlockDenominator:
    name: str
    days: tuple[int, ...]
    sessions: tuple[object, ...]
    ceiling_cents_by_day: Mapping[int, int]
    ceiling_cents_by_asset: Mapping[str, int]
    source_manifest: str
    source_receipt_sha256: str


def _denominator(name: str, path: Path, schema: str) -> MarginBlockDenominator:
    value = _strict_payload(path, schema)
    by_day = {int(day): int(cents) for day, cents
              in dict(value["exact_ceiling_cents_by_day"]).items()}
    by_asset = {str(asset): int(cents) for asset, cents
                in dict(value["exact_ceiling_cents_by_asset"]).items()}
    return MarginBlockDenominator(name, tuple(sorted(by_day)),
        _sessions_from_payload(value["expected_sessions"]), by_day, by_asset,
        str(path), str(value["receipt_sha256"]))


# --------------------------------------------------------------------------
# One replayable day.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MarginDaySource:
    trading_day: int
    universe: DayOptionUniverse
    component_model: object
    action_model: object
    dense: Callable[[], Sequence[object]]


def _margin_trace_identity(*, day: int, universe_representation: str,
        component_receipt: str, action_receipt: str, feature_schema: object,
        calibration: object, admission: AdmissionContract) -> str:
    """Cache identity for an A1 MARGIN trace.

    Distinct schema string from the chain's ``_trace_identity`` on purpose:
    an A1 trace must never be able to land in, or be read from, a chain trace
    directory.  Both walk implementations are hashed in because the MARGIN
    arithmetic lives in the twin.
    """

    from engine.entry_v2 import tabular_live_replay, tabular_walk_twin
    return C.object_sha256({"schema": "QRE2A1MARGINTRACEIDENTITY1",
        "day": int(day), "policy_mode": "MARGIN",
        "universe": universe_representation,
        "component": component_receipt, "action": action_receipt,
        "feature_schema": feature_schema.receipt_sha256,
        "calibration": calibration.receipt_sha256,
        "admission": admission.receipt_sha256,
        "live_implementation": C.file_sha256(
            Path(tabular_live_replay.__file__)),
        "twin_implementation": C.file_sha256(
            Path(tabular_walk_twin.__file__)), "h2_open_count": 0})


def margin_walk_block(*, sources: Iterable[MarginDaySource],
        admissions: Sequence[AdmissionContract], calibration: object,
        feature_schema: object, trace_root: Path,
        margin_report: str) -> tuple[tuple[object, ...], ...]:
    """Replay one block under MARGIN for every admission row.

    Returns one trace tuple per admission, day-ordered.  Engagement guard
    (spec item 4): a block whose EVERY admission row selected nothing is the
    inert-native-path failure mode, so it refuses loudly with the margin
    distribution rather than publishing a $0 row.
    """

    rows = tuple(admissions)
    if not rows:
        raise RecoveryRefusal("A1 margin block has no admission contracts")
    by_index: dict[int, list[object]] = {index: [] for index in range(len(rows))}
    for source in sources:
        # One access: representation_sha256 re-validates the whole universe.
        representation = source.universe.representation_sha256
        targets = [trace_root / _margin_trace_identity(day=source.trading_day,
            universe_representation=representation,
            component_receipt=source.component_model.receipt_sha256,
            action_receipt=source.action_model.receipt_sha256,
            feature_schema=feature_schema, calibration=calibration,
            admission=admission) / f"{source.trading_day}.json"
            for admission in rows]
        cached: dict[int, object] = {}
        for index, target in enumerate(targets):
            if target.is_file():
                cached[index] = load_policy_day_trace(target)
        if len(cached) == len(rows):
            for index in range(len(rows)):
                by_index[index].append(cached[index])
            print(f"    day {source.trading_day} cached", flush=True)
            continue
        started = time.time()
        fresh = replay_policy_day_multistate(admissions=rows,
            universe=source.universe, dense_feature_shards=source.dense(),
            feature_schema=feature_schema,
            component_model=source.component_model,
            action_model=source.action_model, calibration=calibration,
            policy_mode="MARGIN")
        if len(fresh) != len(rows):
            raise RecoveryRefusal(
                f"A1 margin walk returned {len(fresh)} traces for {len(rows)} "
                "admission contracts")
        for index, (trace, target) in enumerate(zip(fresh, targets)):
            if index in cached:
                if trace.receipt_sha256 != cached[index].receipt_sha256:
                    raise RecoveryRefusal(
                        f"cached A1 trace receipt differs at {target}")
            else:
                save_policy_day_trace(trace, target)
                if load_policy_day_trace(target).receipt_sha256 \
                        != trace.receipt_sha256:
                    raise RecoveryRefusal("A1 trace strict reload differs")
            by_index[index].append(trace)
        print(f"    day {source.trading_day} walked in "
              f"{time.time() - started:.1f}s", flush=True)
    if not any(row.selected_opportunity_ids
               for traces in by_index.values() for row in traces):
        raise RecoveryRefusal(
            "A1 margin block selected nothing at ANY of the "
            f"{len(rows)} thresholds - arrivals are not possible on this "
            f"block; margin distribution: {margin_report}")
    return tuple(tuple(by_index[index]) for index in range(len(rows)))


# --------------------------------------------------------------------------
# Real-artifact context.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class MarginRoundTwo:
    """The published round-2 curriculum, receipt-verified, matrices unread.

    WHY not ``load_two_round_curriculum``: it re-loads the 1.47M x 1,764
    component matrix and re-hashes every teacher/feature shard (~11 min per
    process here).  A1 consumes only rosters, OOF tables and the schema, and
    each of those is bound to the manifest receipt below.
    """

    feature_schema: object
    manifest_path: str
    receipt_sha256: str
    component_roster_paths: Mapping[str, str]
    action_roster_paths: Mapping[str, str]
    action_oof_paths: Mapping[str, str]
    component_roster_receipts: Mapping[str, tuple[str, ...]]
    action_roster_receipts: Mapping[str, tuple[str, ...]]

    def roster(self, kind: str, lane: str, seed: int) -> object:
        paths = (self.component_roster_paths if kind == "COMPONENT"
                 else self.action_roster_paths)
        receipts = (self.component_roster_receipts if kind == "COMPONENT"
                    else self.action_roster_receipts)
        rows = load_seed_rosters(paths[lane])
        if tuple(row.receipt_sha256 for row in rows) != receipts[lane]:
            raise RecoveryRefusal(f"A1 {kind} roster receipts differ ({lane})")
        return next(row for row in rows if row.seed == seed)


@dataclass(frozen=True, slots=True)
class MarginContext:
    config: RecoveryConfig
    chronology: RecoveryChronology
    curriculum_round: MarginRoundTwo
    spec_map: Mapping[int, tuple[object, ...]]
    outcome_map: Mapping[int, tuple[object, ...]]


def load_margin_context() -> MarginContext:
    from engine.entry_v2.tabular_fit_only import _chronology_from_mapping
    from engine.entry_v2.tabular_orchestration import (
        CURRICULUM_SCHEMA, TWO_ROUND_SCHEMA, _schema_from_mapping,
    )

    config = RecoveryConfig()
    execution = json.loads((E1R_ROOT / "fit_only_execution.json").read_text())
    chronology = _chronology_from_mapping(execution["chronology"])
    if chronology.receipt_sha256 != execution["chronology_receipt_sha256"]:
        raise RecoveryRefusal("A1 chronology receipt differs")
    two_round = _strict_payload(
        Path(str(execution["artifact_paths"]["curriculum"])), TWO_ROUND_SCHEMA)
    if (two_round["chronology_receipt_sha256"] != chronology.receipt_sha256
            or two_round["config_receipt_sha256"] != config.receipt_sha256
            or int(two_round["rollout_rounds_completed"]) != 2
            or len(two_round["round_manifest_paths"]) != 3):
        raise RecoveryRefusal("A1 two-round curriculum manifest differs")
    round_path = Path(str(two_round["round_manifest_paths"][2]))
    final = _strict_payload(round_path, CURRICULUM_SCHEMA)
    if (final["receipt_sha256"] != two_round["round_receipts"][2]
            or final["chronology_receipt_sha256"] != chronology.receipt_sha256
            or final["config_receipt_sha256"] != config.receipt_sha256
            or int(final["round_index"]) != 2):
        raise RecoveryRefusal("A1 round-2 curriculum receipt differs")
    schema = _schema_from_mapping(final["feature_schema"])
    round_two = MarginRoundTwo(schema, str(round_path),
        str(final["receipt_sha256"]),
        {str(key): str(value) for key, value
         in dict(final["component_roster_paths"]).items()},
        {str(key): str(value) for key, value
         in dict(final["action_roster_paths"]).items()},
        {str(key): str(value) for key, value
         in dict(final["action_oof_paths"]).items()},
        {str(key): tuple(map(str, value)) for key, value
         in dict(final["component_roster_receipts"]).items()},
        {str(key): tuple(map(str, value)) for key, value
         in dict(final["action_roster_receipts"]).items()})
    # `materialize_outcome_corpus` refuses any worker count but the
    # authoritative 16, so three concurrent A1 chains would each open a
    # 16-worker pool and put 48 processes on 13.6 cores.  The corpus is warm
    # and this phase is pure manifest resolution: serialize it.
    # Pod-local lock (stale-network-flock, 2026-08-22): the previous lock file on
    # /workspace stayed held by the dead pod's FUSE client and blocked all six
    # resumed lanes forever.
    with pod_local_flock(REPO_ROOT / "artifacts/cache/a1_margin_corpus"):
        specs = discover_authoritative_session_specs(SOURCE_ROOT,
                                                     REHEARSAL_BOUNDS)
        outcomes = materialize_outcome_corpus(specs, CACHE_ROOT,
                                              max_delay_sec=300, workers=16)
    return MarginContext(config, chronology, round_two,
                         _specs_by_day(specs), _outcomes_by_day(outcomes))


def _day_sources(context: MarginContext, *, days: Sequence[int],
        component_roster: object, action_roster: object,
        feature_schema: object) -> Iterator[MarginDaySource]:
    """One day at a time.

    WHY a generator: a DayOptionUniverse is ~0.5 GB and its validating
    receipt property re-scans the whole day, so materializing a 13-day block
    up front cost minutes of wall and gigabytes of RSS before the first walk.
    The chain builds one universe per day inside its loop; so does this.
    """

    loaded: dict[str, object] = {}

    def bundle(loader, fold) -> object:
        key = f"{loader.__name__}:{fold.bundle_path}"
        if key not in loaded:
            model = loader(fold.bundle_path)
            if model.receipt_sha256 != fold.bundle_receipt_sha256:
                raise RecoveryRefusal("A1 fold model strict load differs")
            loaded[key] = model
        return loaded[key]

    for day in days:
        outcome_rows = context.outcome_map[day]
        shards = tuple(DelayedOutcomeShard.load(row.artifact_path)
                       for row in outcome_rows)
        horizons = {int(row.max_delay_sec) for row in shards}
        if len(horizons) != 1:
            raise RecoveryRefusal("A1 day outcome horizons differ")
        materialized = {row.session for row in outcome_rows}
        day_specs = tuple(row for row in context.spec_map.get(day, ())
                          if row.session in materialized)
        if len(day_specs) != len(outcome_rows):
            raise RecoveryRefusal("A1 day spec/outcome roster differs")
        horizon = int(next(iter(horizons)))
        yield MarginDaySource(day,
            DayOptionUniverse.from_shards(shards),
            bundle(load_component_model, component_roster.bundle_for_day(day)),
            bundle(load_action_model, action_roster.bundle_for_day(day)),
            (lambda rows=day_specs, delay=horizon: tuple(
                load_or_materialize_dense_session(row, max_delay_sec=delay)
                for row in rows)))


def margin_theta_bank(*, action_oof_path: str, chronology: RecoveryChronology,
        calibration: object) -> tuple[np.ndarray, tuple[float, ...], str]:
    """The 21 OOF-margin quantiles for one (lane, seed) (spec item 3b)."""

    prediction = ActionPredictionTable.load(action_oof_path)
    prediction.validate()
    local = ((prediction.day >= chronology.platt[0])
             & (prediction.day <= chronology.platt[1]))
    regret = np.asarray(prediction.predicted_regret_usd, np.float64)[local]
    if not len(regret):
        raise RecoveryRefusal("A1 OOF margin bank is empty")
    margin = regret[:, 1] - regret[:, 0]
    thresholds = tuple(map(float, np.quantile(
        margin, np.linspace(0, 1, A1_QUANTILES))))
    provisional = C.object_sha256({"schema": "QRE2A1MARGINBANK1",
        "calibration": calibration.receipt_sha256,
        "chronology": chronology.receipt_sha256,
        "oof_receipt": prediction.receipt_sha256,
        "margins": _array_sha256(margin),
        "thresholds": thresholds, "quantiles": A1_QUANTILES,
        "h2_open_count": 0})
    return margin, thresholds, provisional


def _evidence_rows(evidence) -> Mapping[str, object]:
    evaluation = evidence.evaluation
    by_asset_day: dict[str, float] = {}
    for row in evaluation.asset_day_results:
        by_asset_day[f"{row.asset}:{row.trading_day}"] = float(row.pnl_usd)
    ceiling_by_asset = dict(evidence.exact_ceiling_usd_by_asset)
    return {"total_pnl_usd": float(evaluation.total_pnl_usd),
        "trades": int(evaluation.trades),
        "usd_per_trade": float(evaluation.usd_per_trade),
        "max_drawdown_usd": float(evaluation.max_drawdown_usd),
        "exact_ceiling_usd": float(evidence.exact_ceiling_usd),
        "ceiling_capture": (float(evaluation.total_pnl_usd)
                            / float(evidence.exact_ceiling_usd)),
        "active_portfolio_days": len(evidence.active_portfolio_days),
        "by_asset": {row.asset: {"total_pnl_usd": float(row.total_pnl_usd),
            "asset_days": int(row.asset_days), "trades": int(row.trades),
            "usd_per_asset_day": float(row.usd_per_asset_day),
            "usd_per_trade": float(row.usd_per_trade),
            "max_drawdown_usd": float(row.max_drawdown_usd),
            "exact_ceiling_usd": float(ceiling_by_asset[row.asset]),
            "exact_ceiling_usd_per_asset_day": (
                float(ceiling_by_asset[row.asset]) / int(row.asset_days)),
            "ceiling_capture": (float(row.total_pnl_usd)
                                / float(ceiling_by_asset[row.asset])
                                if ceiling_by_asset[row.asset] else 0.0)}
            for row in evaluation.by_asset},
        "usd_by_asset_day": dict(sorted(by_asset_day.items()))}


def run_margin_seed(*, lane: str, seed: int,
                    context: MarginContext) -> Mapping[str, object]:
    """SELECTION on the threshold block, then FORWARD at the chosen theta."""

    lane = str(lane).lower()
    if lane not in {"real", "shuffle"}:
        raise RecoveryRefusal("A1 lane is unknown")
    final = context.curriculum_round
    key = f"{lane}:{seed}"
    component_roster = final.roster("COMPONENT", lane, seed)
    action_roster = final.roster("ACTION", lane, seed)
    calibration = load_calibration_bundle(
        E1R_ROOT / "evaluation/calibration" / lane / f"seed_{seed}.json")
    schema = final.feature_schema
    threshold_block = _denominator("THRESHOLD",
        E1R_ROOT / "evaluation/threshold" / lane / f"seed_{seed}"
        / "threshold_selection.json", THRESHOLD_STORE_SCHEMA)
    forward_block = _denominator("FORWARD",
        E1R_ROOT / "evaluation/E1R_frozen_FORWARD" / lane / f"seed_{seed}"
        / "calibrated_block.json", BLOCK_RESULT_SCHEMA)
    margin, thresholds, provisional = margin_theta_bank(
        action_oof_path=final.action_oof_paths[key], chronology=context.chronology,
        calibration=calibration)
    report = json.dumps({"n": int(len(margin)),
        "min": float(np.min(margin)), "max": float(np.max(margin)),
        "quantiles": [round(value, 4) for value in thresholds]})
    admissions = tuple(AdmissionContract(
        context.config.admission_minimum_current_q20_usd,
        context.config.admission_maximum_wall_probability,
        context.config.admission_maximum_adverse_q90_usd, value, index,
        calibration.receipt_sha256, provisional)
        for index, value in enumerate(thresholds))
    root = DIAG_ROOT / lane / f"seed_{seed}"

    print(f"[{key}] SELECTION over {len(threshold_block.days)} days "
          f"x {len(admissions)} thetas", flush=True)
    started = time.time()
    selection_traces = margin_walk_block(
        sources=_day_sources(context, days=threshold_block.days,
            component_roster=component_roster, action_roster=action_roster,
            feature_schema=schema),
        admissions=admissions, calibration=calibration, feature_schema=schema,
        trace_root=root / "traces/threshold", margin_report=report)
    selection_wall = time.time() - started
    evidence_by_index = {index: replay_policy_block(traces,
        expected_sessions=threshold_block.sessions,
        exact_ceiling_cents_by_day=threshold_block.ceiling_cents_by_day,
        exact_ceiling_cents_by_asset=threshold_block.ceiling_cents_by_asset)
        for index, traces in enumerate(selection_traces)}
    by_threshold = {thresholds[index]: value
                    for index, value in evidence_by_index.items()}
    selection = select_threshold_from_calibration_bank(
        lower_advantage_usd=margin,
        replay_at_threshold=lambda value: by_threshold[float(value)],
        calibration_receipt_sha256=calibration.receipt_sha256,
        config=context.config)
    if tuple(selection.thresholds_usd) != thresholds:
        raise RecoveryRefusal("A1 selection law rebuilt a different theta bank")
    # Same trial/evidence binding the chain's own selector asserts: duplicate
    # quantile values collapse in `by_threshold`, and this is what catches it.
    for index, trial in enumerate(selection.trials):
        if trial.gate.receipt_sha256 != evaluate_economic_gate(
                evidence_by_index[index], config=context.config).receipt_sha256:
            raise RecoveryRefusal(
                f"A1 threshold trial {index} gate differs from its evidence")
    chosen = AdmissionContract(
        context.config.admission_minimum_current_q20_usd,
        context.config.admission_maximum_wall_probability,
        context.config.admission_maximum_adverse_q90_usd,
        selection.selected_threshold_usd, selection.selected_quantile_index,
        calibration.receipt_sha256, selection.receipt_sha256)

    print(f"[{key}] theta q{selection.selected_quantile_index} = "
          f"{selection.selected_threshold_usd:.4f} "
          f"(floor_feasible={selection.floor_feasible}); FORWARD over "
          f"{len(forward_block.days)} days", flush=True)
    started = time.time()
    forward_traces = margin_walk_block(
        sources=_day_sources(context, days=forward_block.days,
            component_roster=component_roster, action_roster=action_roster,
            feature_schema=schema),
        admissions=(chosen,), calibration=calibration, feature_schema=schema,
        trace_root=root / "traces/forward", margin_report=report)[0]
    forward_wall = time.time() - started
    forward_evidence = replay_policy_block(forward_traces,
        expected_sessions=forward_block.sessions,
        exact_ceiling_cents_by_day=forward_block.ceiling_cents_by_day,
        exact_ceiling_cents_by_asset=forward_block.ceiling_cents_by_asset)
    forward_gate = evaluate_economic_gate(forward_evidence,
                                          config=context.config)
    selected_gate = evaluate_economic_gate(
        evidence_by_index[selection.selected_quantile_index],
        config=context.config)
    core = {"schema": A1_SEED_SCHEMA, "spec": "design/A1_MARGIN_RULE_SPEC.md",
        "lane": lane, "seed": int(seed), "policy_mode": "MARGIN",
        "diagnostic_only": True, "chain_default_changed": False,
        "theta_bank_usd": thresholds,
        "theta_bank_rows": int(len(margin)),
        "theta_bank_receipt_sha256": provisional,
        "selected_quantile_index": selection.selected_quantile_index,
        "selected_threshold_usd": selection.selected_threshold_usd,
        "floor_feasible": bool(selection.floor_feasible),
        "selection_receipt_sha256": selection.receipt_sha256,
        "admission_receipt_sha256": chosen.receipt_sha256,
        "calibration_receipt_sha256": calibration.receipt_sha256,
        "component_roster_receipt_sha256": component_roster.receipt_sha256,
        "action_roster_receipt_sha256": action_roster.receipt_sha256,
        "threshold_denominator": {"manifest": threshold_block.source_manifest,
            "receipt_sha256": threshold_block.source_receipt_sha256},
        "forward_denominator": {"manifest": forward_block.source_manifest,
            "receipt_sha256": forward_block.source_receipt_sha256},
        "threshold_trials": tuple({
            "quantile_index": row.quantile_index,
            "threshold_usd": row.threshold_usd,
            "weekly_lcb_usd_per_active_day": row.weekly_lcb_usd_per_active_day,
            "trades": row.gate.trades,
            "total_pnl_usd": row.gate.total_pnl_usd,
            "floor_pass": row.gate.floor_pass} for row in selection.trials),
        "threshold_selected": _evidence_rows(
            evidence_by_index[selection.selected_quantile_index]),
        "threshold_selected_gate": selected_gate.receipt_sha256,
        "forward": _evidence_rows(forward_evidence),
        "forward_gate": forward_gate.receipt_sha256,
        "forward_gate_detail": {"floor_pass": forward_gate.floor_pass,
            "laws_pass": forward_gate.laws_pass,
            "reasons": tuple(forward_gate.reasons)},
        "goal_ladder_usd_per_asset_day": A1_GOAL_LADDER_USD,
        # Theta is picked by `evaluate_economic_gate`.  A concurrent lane owns
        # that function (RAIL-0 ladder), so the bytes it ran under are part of
        # this receipt: a 10-seed table assembled across two gate versions is
        # not one measurement, and this is what makes that detectable.
        "economic_gate_implementation_sha256": C.file_sha256(
            Path(REPO_ROOT / "engine/entry_v2/tabular_calibration.py")),
        "config_receipt_sha256": context.config.receipt_sha256,
        "trace_receipts": {"threshold": tuple(
                row.receipt_sha256 for row in selection_traces[
                    selection.selected_quantile_index]),
            "forward": tuple(row.receipt_sha256 for row in forward_traces)},
        "selection_wall_sec": round(selection_wall, 1),
        "forward_wall_sec": round(forward_wall, 1),
        "h2_open_count": 0}
    receipt = _publish(root / "margin_rule_seed.json", core)
    print(f"[{key}] published {root/'margin_rule_seed.json'} {receipt}",
          flush=True)
    return {**core, "receipt_sha256": receipt}


# --------------------------------------------------------------------------
# Summary over the ten published per-seed receipts.
# --------------------------------------------------------------------------

def _mean_sd(values: Sequence[float]) -> tuple[float, float]:
    array = np.asarray(tuple(values), np.float64)
    return float(array.mean()), float(array.std(ddof=1)) if len(array) > 1 \
        else 0.0


def _one_gate_implementation(rows: Mapping[str, Mapping[str, object]]) -> str:
    """Refuse a summary assembled across two economic-gate versions."""

    hashes = {str(value["economic_gate_implementation_sha256"])
              for value in rows.values()}
    if len(hashes) != 1:
        raise RecoveryRefusal(
            "A1 seeds were judged under different economic-gate bytes: "
            + json.dumps({key: value["economic_gate_implementation_sha256"]
                          for key, value in sorted(rows.items())}))
    return next(iter(hashes))


def build_summary(seeds: Sequence[int]) -> Mapping[str, object]:
    rows = {}
    for lane in ("real", "shuffle"):
        for seed in seeds:
            path = DIAG_ROOT / lane / f"seed_{seed}" / "margin_rule_seed.json"
            rows[f"{lane}:{seed}"] = _strict_payload(path, A1_SEED_SCHEMA)
    assets = tuple(C.ASSETS)
    per_asset = {}
    for asset in assets:
        summary = {}
        for lane in ("real", "shuffle"):
            values = [float(rows[f"{lane}:{seed}"]["forward"]["by_asset"]
                            [asset]["usd_per_asset_day"]) for seed in seeds]
            mean, sd = _mean_sd(values)
            summary[lane] = {"values": values, "mean": mean, "sd": sd}
        summary["weakest_real"] = min(summary["real"]["values"])
        summary["strongest_shuffle"] = max(summary["shuffle"]["values"])
        summary["separated"] = (summary["weakest_real"]
                                > summary["strongest_shuffle"])
        summary["exact_ceiling_usd_per_asset_day"] = float(
            rows[f"real:{seeds[0]}"]["forward"]["by_asset"][asset]
            ["exact_ceiling_usd_per_asset_day"])
        per_asset[asset] = summary
    block = {}
    for field in ("total_pnl_usd", "trades", "usd_per_trade",
                  "max_drawdown_usd", "ceiling_capture"):
        entry = {}
        for lane in ("real", "shuffle"):
            values = [float(rows[f"{lane}:{seed}"]["forward"][field])
                      for seed in seeds]
            mean, sd = _mean_sd(values)
            entry[lane] = {"values": values, "mean": mean, "sd": sd}
        block[field] = entry
    core = {"schema": A1_SUMMARY_SCHEMA, "spec": "design/A1_MARGIN_RULE_SPEC.md",
        "policy_mode": "MARGIN", "diagnostic_only": True,
        "seeds": tuple(int(seed) for seed in seeds),
        "goal_ladder_usd_per_asset_day": A1_GOAL_LADDER_USD,
        "forward_usd_per_asset_day": per_asset, "forward_block": block,
        "selected_theta_usd": {key: value["selected_threshold_usd"]
                               for key, value in sorted(rows.items())},
        "selected_quantile_index": {key: value["selected_quantile_index"]
                                    for key, value in sorted(rows.items())},
        "floor_feasible": {key: value["floor_feasible"]
                           for key, value in sorted(rows.items())},
        "economic_gate_implementation_sha256": _one_gate_implementation(rows),
        "seed_receipts": {key: value["receipt_sha256"]
                          for key, value in sorted(rows.items())},
        "h2_open_count": 0}
    receipt = _publish(DIAG_ROOT / "margin_rule_summary.json", core)
    return {**core, "receipt_sha256": receipt}


# --------------------------------------------------------------------------
# Guards.
# --------------------------------------------------------------------------

def argmin_guard() -> Mapping[str, object]:
    """D-017: the ARGMIN default reproduces a PUBLISHED trace byte for byte."""

    context = load_margin_context()
    lane, seed = "real", context.config.real_seeds[0]
    manifest = json.loads((E1R_ROOT / "evaluation/E1R_frozen_FORWARD" / lane
                           / f"seed_{seed}" / "calibrated_block.json").read_text())
    stored_path = Path(str(manifest["trace_paths"][0]))
    stored = load_policy_day_trace(stored_path)
    day = stored.trading_day
    final = context.curriculum_round
    component_roster = final.roster("COMPONENT", lane, seed)
    action_roster = final.roster("ACTION", lane, seed)
    calibration = load_calibration_bundle(
        E1R_ROOT / "evaluation/calibration" / lane / f"seed_{seed}.json")
    # The block manifest stores the admission RECEIPT; the contract itself
    # lives in the threshold bank the block was replayed at.
    _selection, admission = load_threshold_bank(
        E1R_ROOT / "evaluation/threshold" / lane / f"seed_{seed}"
        / "threshold_selection.json")
    if admission.receipt_sha256 != manifest["admission"]:
        raise RecoveryRefusal("A1 guard admission differs from the block")
    source = _day_sources(context, days=(day,),
        component_roster=component_roster, action_roster=action_roster,
        feature_schema=final.feature_schema)[0]
    replayed = replay_policy_day(universe=source.universe,
        dense_feature_shards=source.dense(),
        feature_schema=final.feature_schema,
        component_model=source.component_model,
        action_model=source.action_model, mode="CALIBRATED",
        calibration=calibration, admission=admission)
    result = {"day": day, "stored_trace": str(stored_path),
        "stored_receipt_sha256": stored.receipt_sha256,
        "replayed_receipt_sha256": replayed.receipt_sha256,
        "policy_mode": replayed.policy_mode,
        "identical": replayed.receipt_sha256 == stored.receipt_sha256}
    if not result["identical"] or replayed.policy_mode != "ARGMIN":
        raise RecoveryRefusal(f"ARGMIN default is no longer byte-identical: "
                              f"{json.dumps(result)}")
    _publish(DIAG_ROOT / "argmin_byte_identity_guard.json",
             {"schema": "QRE2A1ARGMINGUARD1", **result, "h2_open_count": 0})
    return result


def selftest() -> int:
    """Synthetic-bundle checks, including the zero-arrival refusal."""

    import unittest
    from engine.entry_v2.test_tabular_walk_twin import (
        _WtwinCalibrationStub, _wtwin_admission, _wtwin_fixture,
    )

    class MarginRunnerSelfTest(unittest.TestCase):

        def _sources(self, count=1):
            fixture = _wtwin_fixture()
            component = fixture["component_model"]
            action = fixture["action_model"]
            return (MarginDaySource(int(fixture["universe"].trading_day),
                fixture["universe"], component, action,
                lambda shards=fixture["dense_feature_shards"]: shards),), \
                fixture["feature_schema"]

        def test_walk_block_publishes_and_resumes_traces(self):
            import tempfile
            sources, schema = self._sources()
            admissions = tuple(_wtwin_admission(value, index)
                               for index, value in enumerate((-1e6, 0.0, 3.0)))
            with tempfile.TemporaryDirectory(
                    dir=str(REPO_ROOT / "artifacts")) as room:
                root = Path(room) / "traces"
                first = margin_walk_block(sources=sources,
                    admissions=admissions, calibration=_WtwinCalibrationStub(),
                    feature_schema=schema, trace_root=root,
                    margin_report="{}")
                resumed = margin_walk_block(sources=sources,
                    admissions=admissions, calibration=_WtwinCalibrationStub(),
                    feature_schema=schema, trace_root=root,
                    margin_report="{}")
            self.assertEqual(
                tuple(row[0].receipt_sha256 for row in first),
                tuple(row[0].receipt_sha256 for row in resumed))
            self.assertEqual(first[0][0].policy_mode, "MARGIN")
            self.assertTrue(first[0][0].selected_opportunity_ids)

        def test_zero_arrival_block_refuses_with_the_distribution(self):
            import tempfile
            sources, schema = self._sources()
            # Every theta unreachable: no margin can clear 1e9 dollars.
            admissions = tuple(_wtwin_admission(1.0e9, index)
                               for index in range(3))
            with tempfile.TemporaryDirectory(
                    dir=str(REPO_ROOT / "artifacts")) as room:
                with self.assertRaises(RecoveryRefusal) as caught:
                    margin_walk_block(sources=sources, admissions=admissions,
                        calibration=_WtwinCalibrationStub(),
                        feature_schema=schema,
                        trace_root=Path(room) / "traces",
                        margin_report='{"quantiles": [-8.0, 0.0, 4.0]}')
            self.assertIn("arrivals are not possible", str(caught.exception))
            self.assertIn("quantiles", str(caught.exception))

        def test_mean_sd_is_the_sample_deviation(self):
            mean, sd = _mean_sd((1.0, 2.0, 3.0))
            self.assertAlmostEqual(mean, 2.0)
            self.assertAlmostEqual(sd, 1.0)

    suite = unittest.TestLoader().loadTestsFromTestCase(MarginRunnerSelfTest)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() \
        else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--argmin-guard", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--lane", choices=("real", "shuffle"))
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.argmin_guard:
        print(json.dumps(dict(argmin_guard()), sort_keys=True))
        return 0
    if args.summary:
        print(json.dumps(C.canonical_json_value(
            dict(build_summary(RecoveryConfig().real_seeds))), sort_keys=True))
        return 0
    if args.lane is None or args.seed is None:
        parser.error("--lane and --seed are required for a measurement run")
    run_margin_seed(lane=args.lane, seed=args.seed,
                    context=load_margin_context())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
