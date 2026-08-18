from __future__ import annotations

from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
import unittest

import numpy as np
import torch
from safetensors.torch import save

from . import common as C
from . import campaign as CP
from .capacity_contract import capacity_eligibility
from .atlas_statistics import PairedObservationRecord, SupportKind
from .causal_label_atlas import PROBE_REGISTRY
from .neural_sufficiency_stage_engine import (
    AssetEconomics, E1ScreenResult, ExactHeldStageEngine, HeldWinnerArtifacts,
    MeasuredFinalistConfirmation, MeasuredProbeScreen, ProbeSupportInputs,
    execute_e1_screen,
)
from .neural_sufficiency_stage_persistence import (
    CrashResumableHeldStageEngine, InjectedBoundaryCrash,
    StageBoundaryStore, StageNumericalArtifacts, StagePersistenceRefusal,
)
from .neural_winner_artifact import required_payloads_for_head
from .selected_horizon_contract import (
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
    TARGET_LAW_SHA256 as SELECTED_HORIZON_TARGET_LAW_SHA256,
)
from .test_campaign import _fold_result
from .train import (
    ARM_FULL_PREFIX, SELECTED_ACTION_FIT_WEIGHT_LAW,
    SELECTED_ORDINAL_SEMANTICS_SHA256, SELECTED_PHASE_PAIR_LAW,
    SELECTED_POLICY_CHRONOLOGY_LAW, SELECTED_POLICY_TRAINING_SCHEMA,
    SelectedFoldTrainingReceipt,
    build_selected_winner_fold_report,
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(value):
    raw = value if isinstance(value, bytes) else str(value).encode()
    return hashlib.sha256(raw).hexdigest()


def _json(schema: str, **values) -> bytes:
    return _canonical({"schema": schema, **values})


def _npz(**arrays) -> bytes:
    stream = io.BytesIO(); np.savez(stream, **arrays); return stream.getvalue()


def _screens() -> tuple[MeasuredProbeScreen, ...]:
    assets = np.repeat(np.asarray(["HG", "NKD", "SI"]), 200)
    fit_days = np.tile(np.arange(20210601, 20210621), 30)[:600]
    values = np.linspace(-3, 3, 600)
    held_days = [20211101 + index for index in range(20)]
    records = tuple(PairedObservationRecord(
        f"c{index:04d}", str(assets[index]), str(held_days[index % 20]), True,
        _sha("real-target"), _sha("twin-target"),
        1.0 + .05 * np.sin(index), .2 * np.cos(index),
    ) for index in range(600))
    base = MeasuredProbeScreen(
        "C01P01", "mixed-event", "SHARED_PRETEXT", "shallow_probe", records,
        ProbeSupportInputs(SupportKind.CONTINUOUS, assets, np.ones(600, bool),
                           values=values, day=fit_days,
                           censored=np.zeros(600, bool),
                           selected_horizon_start_d8=20210531),
        values, _sha("real-checkpoint"), _sha("twin-checkpoint"), _sha("rows"),
        (20211001, 20211004, 20211005, 20211006,
         20211007, 20211008, 20211011),
        {"real_funnel": _sha("real-funnel"), "twin_funnel": _sha("twin-funnel")},
    )
    unavailable = tuple(replace(
        base, probe_id=spec.probe_id, records=(), real_checkpoint_sha256="0" * 64,
        twin_checkpoint_sha256="0" * 64, path_receipts={},
        availability="UNAVAILABLE_LOW_SUPPORT",
    ) for spec in PROBE_REGISTRY if spec.probe_id != base.probe_id)
    return (base, *unavailable)


def _e1_numerical(result: E1ScreenResult) -> StageNumericalArtifacts:
    payloads = {
        "pretext/C01P01.checkpoint.npz": _npz(weight=np.arange(8, dtype=np.float32)),
        "pretext/C02P01.checkpoint.npz": _npz(weight=np.arange(9, dtype=np.float32)),
        "fit-contexts.json": _json("entry-v2-e1-fit-contexts-v1", contexts={"C01P01": "a" * 64}),
        "fit-ledger.json": _json("entry-v2-e1-fit-ledger-v1", fits=90),
        "screens.json": _json(
            "entry-v2-e1-complete-screen-evidence-v1",
            registry_probe_ids=[probe.probe_id for probe in PROBE_REGISTRY]),
    }
    payloads["finalists.json"] = _json(
        "entry-v2-e1-finalists-v1", finalists=list(result.finalists),
        finalist_receipt_sha256=result.finalist_receipt_sha256,
        payload_sha256={name: _sha(raw) for name, raw in sorted(payloads.items())},
    )
    return StageNumericalArtifacts.freeze("E1", payloads)


def _winner_payloads() -> dict[str, bytes]:
    target_hash = "3" * 64
    capacity_rows = {}
    for asset in C.ASSETS:
        row = {
            "capacity_regime": "FULL", "included_trading_days": 20,
            "days_with_trades": 20, "trades": 40,
            "total_pnl_usd": 42_000.0, "usd_per_trade": 1_050.0,
            "usd_per_asset_day": 2_100.0,
            "chronological_max_drawdown_usd": 450.0,
            "drawdown_p90_usd": 300.0,
            "oracle_total_pnl_usd": 60_000.0,
            "oracle_usd_per_asset_day": 3_000.0, "oracle_capture": 0.7,
            "asset_day_denominator": "included_trading_days",
            "values_clipped": False, "replay_receipt_sha256": "a" * 64,
            "oracle_replay_receipt_sha256": "b" * 64,
        }
        eligibility = capacity_eligibility(row)
        row.update(
            eligibility=("ELIGIBLE" if eligibility.eligible else "INELIGIBLE"),
            threshold_feasibility_sha256=
                eligibility.threshold_feasibility_sha256,
            capacity_eligibility_sha256=eligibility.receipt_sha256,
        )
        capacity_rows[asset] = row
    json_payloads = {
        "arm.json": _json("entry-v2-selected-neural-arm-v1", arm="M1"),
        "objective.json": _json(
            "entry-v2-selected-atlas-objective-v1", registry_id="C01P01",
            target_row_manifest_sha256=target_hash,
        ),
        "normalizers.json": _json("entry-v2-normalizers-v1"),
        "mapper.json": _json("entry-v2-mapper-v1"),
        "calibrator.json": _json("entry-v2-calibrator-v1"),
        "thresholds.json": _json("entry-v2-thresholds-v1",
                                  thresholds={asset: .7 for asset in C.ASSETS}),
        "policy-canary.json": _json("entry-v2-policy-canary-v1", passed=True),
        "capacity.json": _json(
            "entry-v2-capacity-authority-v2",
            values_clipped=False,
            asset_day_denominator="included_trading_days",
            per_asset=capacity_rows,
        ),
        "source-manifest.json": _json("entry-v2-source-manifest-v1"),
        "row-manifest.json": _json(
            "entry-v2-row-manifest-v1", target_row_manifest_sha256=target_hash,
        ),
    }
    tensor = save({"weight": torch.arange(4, dtype=torch.float32)})
    payloads = {
        **json_payloads, "encoder.safetensors": tensor,
        "head.safetensors": tensor, "objective-head.safetensors": tensor,
        "direct-policy.safetensors": tensor,
    }
    self_required = set(required_payloads_for_head("direct_neural"))
    assert set(payloads) == self_required
    return payloads


def _confirmation(payloads: dict[str, bytes]) -> MeasuredFinalistConfirmation:
    days = tuple(range(20220610, 20220630))
    platt_days = (20220314, 20220401, 20220427)
    threshold_development_days = (20220428, 20220516, 20220609)
    effects = {asset: np.linspace(80, 120, len(days)) + index
               for index, asset in enumerate(C.ASSETS)}
    capture = {asset: np.linspace(.2, .4, len(days)) + index * .01
               for index, asset in enumerate(C.ASSETS)}
    capacity = _sha(payloads["capacity.json"])
    capacity_document = json.loads(payloads["capacity.json"])
    economics = {}
    for asset in C.ASSETS:
        row = capacity_document["per_asset"][asset]
        economics[asset] = AssetEconomics(
            row["capacity_regime"], row["included_trading_days"], row["trades"],
            row["total_pnl_usd"], row["usd_per_trade"], row["usd_per_asset_day"],
            row["chronological_max_drawdown_usd"], row["drawdown_p90_usd"],
            row["oracle_total_pnl_usd"], row["oracle_usd_per_asset_day"],
            row["oracle_capture"], row["replay_receipt_sha256"],
            row["oracle_replay_receipt_sha256"], capacity,
            row["days_with_trades"], row["threshold_feasibility_sha256"],
            row["capacity_eligibility_sha256"], row["eligibility"],
        )
    return MeasuredFinalistConfirmation(
        "C01P01", "M1", "direct_neural", days, effects, capture, economics,
        _sha(payloads["arm.json"]), _sha(payloads["objective.json"]),
        _sha(payloads["calibrator.json"]), _sha(payloads["thresholds.json"]),
        capacity, _sha(payloads["mapper.json"]), _sha("e2-real"), _sha("e2-twin"),
        1000, 2.0, (20210531, 20220311),
        (*platt_days, *threshold_development_days), days,
        platt_days=platt_days,
        threshold_development_days=threshold_development_days,
    )


def _confirmation_matrix(
    selected: MeasuredFinalistConfirmation,
) -> tuple[MeasuredFinalistConfirmation, ...]:
    rows = []
    for arm in ("C0", "C1", "L0", "L1", "M1"):
        for decision in ("direct_neural", "catboost"):
            if (arm, decision) == ("M1", "direct_neural"):
                rows.append(selected)
                continue
            tag = f"{arm}:{decision}"
            rows.append(replace(
                selected,
                probe_id=("A0_CURRENT_GROUPING" if arm == "C0" else "C01P01"),
                arm=arm,
                decision_kind=decision,
                economics=MappingProxyType({}),
                selected_arm_sha256=_sha(f"arm:{tag}"),
                selected_objective_sha256=_sha(f"objective:{tag}"),
                calibrator_sha256=_sha(f"calibrator:{tag}"),
                thresholds_sha256=_sha(f"thresholds:{tag}"),
                capacity_authority_sha256=_sha(f"capacity:{tag}"),
                mapper_sha256=_sha(f"mapper:{tag}"),
                real_checkpoint_sha256=_sha(f"real:{tag}"),
                twin_checkpoint_sha256=_sha(f"twin:{tag}"),
                status="NO_FEASIBLE_THRESHOLD",
                rejection_reason_by_asset=MappingProxyType({
                    asset: "NO_FEASIBLE_THRESHOLD" for asset in C.ASSETS
                }),
                funnel_receipt_by_asset=MappingProxyType({
                    asset: _sha(f"funnel:{tag}:{asset}") for asset in C.ASSETS
                }),
            ))
    return tuple(rows)


def _e2_numerical(payloads: dict[str, bytes], confirmation: MeasuredFinalistConfirmation,
                  objective_freeze_receipt_sha256: str) -> StageNumericalArtifacts:
    numerical = {
        "encoder.safetensors": payloads["encoder.safetensors"],
        "head.safetensors": payloads["head.safetensors"],
        "objective-head.safetensors": payloads["objective-head.safetensors"],
        "mapper.json": payloads["mapper.json"],
        "calibrator.json": payloads["calibrator.json"],
        "thresholds.json": payloads["thresholds.json"],
        "capacity.json": payloads["capacity.json"],
        "compact-targets.npz": _npz(values=np.arange(12).reshape(3, 4),
                                     valid=np.ones(3, bool)),
        "compact-context.json": _json("entry-v2-compact-context-v1", context="b" * 64),
    }
    normalizer = {
        "schema": "entry-v2-selected-horizon-normalizer-v1",
        "coordinates": [300, 600, 900, 1200, 1800, "FINAL"],
        "target_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
        "target_law_sha256": SELECTED_HORIZON_TARGET_LAW_SHA256,
        "location": [0.0] * 6, "scale": [1.0] * 6,
    }
    normalizer["receipt_sha256"] = _sha(_canonical(normalizer))
    numerical["selected-horizon-normalizer.json"] = _canonical(normalizer)
    roster = {
        "schema": "entry-v2-e2-validation-roster-v1",
        "days": [20220201], "candidate_ids": ["candidate-1"],
        "weighting": "UNWEIGHTED_VALID_ROWS",
        "selected_horizon_normalizer_sha256": normalizer["receipt_sha256"],
    }
    roster["receipt_sha256"] = _sha(_canonical(roster))
    numerical["validation-roster.json"] = _canonical(roster)
    numerical["arm-authorization.json"] = _json(
        "entry-v2-e2-arm-authorization-v1", selected_arm=confirmation.arm,
        five_arm_checkpoint_sha256={arm: _sha(f"checkpoint:{arm}")
                                    for arm in ("C0", "C1", "L0", "L1", "M1")},
        ten_path_receipt_sha256={
            f"{arm}:{head}": _sha(f"path:{arm}:{head}")
            for arm in ("C0", "C1", "L0", "L1", "M1")
            for head in ("direct_neural", "catboost")},
        base_fit_arms=["C0", "L0", "M1"],
        byte_copies={"C1": "C0", "L1": "L0"},
        training_receipt_sha256=_sha("training"),
        grouped_receipt_sha256=_sha("grouped"),
    )
    numerical["selection.json"] = _json(
        "entry-v2-e2-selection-v1", probe_id=confirmation.probe_id,
        arm=confirmation.arm, decision_head_kind=confirmation.decision_kind,
        selection_hashes={
            "selected_arm_sha256": confirmation.selected_arm_sha256,
            "selected_objective_sha256": confirmation.selected_objective_sha256,
            "calibrator_sha256": confirmation.calibrator_sha256,
            "thresholds_sha256": confirmation.thresholds_sha256,
            "capacity_authority_sha256": confirmation.capacity_authority_sha256,
        },
        objective_freeze_receipt_sha256=objective_freeze_receipt_sha256,
        payload_sha256={name: _sha(raw) for name, raw in sorted(numerical.items())},
    )
    return StageNumericalArtifacts.freeze("E2", numerical)


def _acceptance_m8_payloads() -> dict[str, bytes]:
    tensor = save({"weight": torch.arange(2, dtype=torch.float32)})
    payloads = {f"acceptance/{arm}.competence.safetensors": tensor
                for arm in ("C0", "C1", "L0", "L1", "M1")}
    raw_evidence = {"schema": "entry-v2-raw-fidelity-evidence-v1",
                    "measured": True}
    raw_evidence["receipt_sha256"] = _sha(_canonical(raw_evidence))
    payloads["acceptance/evidence/raw-fidelity.json"] = _canonical(raw_evidence)
    arm_evidence = {}
    for arm in ("C0", "C1", "L0", "L1", "M1"):
        value = {"schema": "entry-v2-arm-competence-evidence-v1",
                 "arm": arm, "measured": True}
        value["receipt_sha256"] = _sha(_canonical(value))
        name = f"acceptance/evidence/arm-{arm}.json"
        payloads[name] = _canonical(value)
        arm_evidence[arm] = name
    authorization = {
        "schema": "entry-v2-accepted-arm-authorization-v1",
        "arms": {arm: {
            "checkpoint_sha256": _sha(tensor),
            "row_manifest_sha256": _sha(f"row:{arm}"),
            "representation_sha256": _sha(f"representation:{arm}"),
            "evidence_sha256": _sha(payloads[arm_evidence[arm]]),
        } for arm in ("C0", "C1", "L0", "L1", "M1")},
        "canonical_arms": ["C0", "C1", "L0", "L1", "M1"],
        "event_schema_sha256": _sha("event-schema"),
        "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
        "selected_horizon_target_law_sha256":
            SELECTED_HORIZON_TARGET_LAW_SHA256,
        "competence_only_discard_before_held": True,
        "raw_fidelity_evidence_sha256": _sha(
            payloads["acceptance/evidence/raw-fidelity.json"]),
    }
    authorization["receipt_sha256"] = _sha(_canonical(authorization))
    payloads["acceptance/arm-authorization.json"] = _canonical(authorization)
    acceptance_manifest = {
        "schema": "entry-v2-acceptance-numerical-manifest-v1",
        "payload_sha256": {name: _sha(raw) for name, raw in sorted(payloads.items())},
    }
    acceptance_manifest["receipt_sha256"] = _sha(_canonical(acceptance_manifest))
    payloads["acceptance/manifest.json"] = _canonical(acceptance_manifest)

    real = sorted(probe.probe_id for probe in PROBE_REGISTRY)
    twin = sorted(f"{probe.probe_id}.SHUFFLED" for probe in PROBE_REGISTRY)
    paths = sorted(f"{arm}:{head}" for arm in ("C0", "C1", "L0", "L1", "M1")
                   for head in ("direct_neural", "catboost"))
    selected_path = "M1:direct_neural"
    goal_receipts = {
        f"{stage}.{role}.{asset}": _sha(f"{stage}:{role}:{asset}")
        for stage in ("E1r", "E2r") for role in ("THRESHOLD", "FORWARD")
        for asset in C.ASSETS}
    path_rows = {name: {"status": "ELIGIBLE"} for name in paths}
    rehearsal = {
        "schema": "entry-v2-fit-only-held-rehearsal-v1", "status": "PASS",
        "held_launch_permitted": True,
        "minimum_oracle_capture": .8,
        "fit_only_max_d8": 20210930, "no_held_labels": True,
        "source_tree_sha256": _sha("source-tree"),
        "e1r": {"probe_screen": {"ledger": {
            probe: {} for probe in real}}},
        "e2r": {"arm_head_matrix": {
            "matrix": path_rows, "winner": selected_path,
            "diagnostic_path": selected_path,
            "selected_objective": real[0],
            "selected_learner_objective": real[0]}},
        "g7": {
            "single_real_path": selected_path,
            "selected_arm": "M1", "selected_head": "direct_neural",
            "selected_objective": real[0],
            "learner_law_sha256": _sha("learner-law"),
            "e1r_checkpoint_sha256": _sha("e1-checkpoint"),
            "e2r_checkpoint_sha256": _sha("e2-checkpoint"),
            "e1r_fit_wall": 20210709, "e2r_fit_wall": 20210813,
            "same_full_learner_independent_fits": True,
            "minimum_oracle_capture": .8,
            "goal_recovery_all_blocks": True,
            "goal_recovery_receipts": goal_receipts,
            "all_asset_in_sample": True,
            "all_asset_disjoint_forward": True,
            "candidate_ceiling_all_blocks": True,
            "twins_counted": False,
        },
    }
    rehearsal["receipt_sha256"] = _sha(_canonical(rehearsal))
    materialized_real = real[0]; materialized_twin = twin[0]
    rows = {name: {"status": ("MATERIALIZED" if name == materialized_real
                              else "UNAVAILABLE_LOW_SUPPORT")} for name in real}
    twin_rows = {name: {"status": ("MATERIALIZED" if name == materialized_twin
                                   else "UNAVAILABLE_LOW_SUPPORT")} for name in twin}
    payloads.update({
        "M8/rehearsal-evidence.json": _canonical(rehearsal),
        "M8/objective-ledger.json": _json(
            "entry-v2-m8-objective-ledger-v1", real_objective_ids=real,
            twin_objective_ids=twin, rows=rows, twin_rows=twin_rows),
        "M8/path-evidence.json": _json(
            "entry-v2-m8-five-arm-ten-path-v1",
            arms=["C0", "C1", "L0", "L1", "M1"],
            paths=path_rows),
        "M8/restart-contract.json": _json(
            "entry-v2-m8-numerical-restart-contract-v2",
            strict_second_process_reload_required=True,
            same_selected_full_learner_required=True,
            source_tree_sha256=_sha("source-tree"),
            diagnostic_semantic_identity_sha256=_sha("semantic-corpus"),
            one_load_id="one-load"),
        "M8/shared/checkpoint.safetensors": tensor,
        "M8/shared/canary-output.npz": _npz(value=np.arange(2)),
        "M8/objective/model.safetensors": tensor,
        "M8/objective/canary.npz": _npz(value=np.arange(2)),
        "M8/pretext/C01.checkpoint.npz": _npz(value=np.arange(2)),
        "M8/pretext/C02.checkpoint.npz": _npz(value=np.arange(2)),
        "M8/pretext/shared-probe-plane.npz": _npz(value=np.arange(2)),
        "M8/selected/final.safetensors": tensor,
        "M8/selected/objective-head.safetensors": tensor,
        "M8/selected/canary-input.npz": _npz(value=np.arange(2)),
        "M8/selected/canary-output.npz": _npz(value=np.arange(2)),
        "M8/selected/training.json": _json(
            "entry-v2-fit-only-selected-full-training-v1"),
        "M8/policy/mapper.json": _json("entry-v2-m8-binding-mapper-v1"),
        "M8/policy/calibrator.json": _json("entry-v2-m8-positive-platt-v1"),
        "M8/policy/thresholds.json": _json("entry-v2-m8-thresholds-v1"),
        "M8/policy/scores.npz": _npz(value=np.arange(2)),
        "M8/policy/replay.json": _json("entry-v2-m8-replay-v1"),
        "M8/policy/model.cbm": b"native-catboost-model",
    })
    arm_checkpoint = ["M8/shared/checkpoint.safetensors"]
    arm_final = [*arm_checkpoint, "M8/shared/canary-output.npz"]
    policy = [
        "M8/policy/mapper.json", "M8/policy/calibrator.json",
        "M8/policy/thresholds.json", "M8/policy/scores.npz",
        "M8/policy/replay.json", "M8/policy/model.cbm",
    ]
    selected = [
        "M8/selected/final.safetensors",
        "M8/selected/objective-head.safetensors",
        "M8/selected/canary-input.npz",
        "M8/selected/canary-output.npz", "M8/selected/training.json",
        *policy,
    ]
    objective_payloads = {
        name: (["M8/objective/model.safetensors",
                "M8/objective/canary.npz"]
               if name in {materialized_real, materialized_twin}
               else ["M8/objective-ledger.json"])
        for name in (*real, *twin)}
    manifest = {
        "schema": "entry-v2-m8-evidence-manifest-v2",
        "source_tree_sha256": _sha("source-tree"),
        "arms": ["C0", "C1", "L0", "L1", "M1"],
        "selectable_paths": paths, "real_objective_ids": real,
        "twin_objective_ids": twin,
        "payload_roles": {
            "rehearsal": ["M8/rehearsal-evidence.json"],
            "objectives": ["M8/objective-ledger.json"],
            "arm_head_paths": ["M8/path-evidence.json"],
            "pretexts": ["M8/pretext/C01.checkpoint.npz",
                         "M8/pretext/C02.checkpoint.npz",
                         "M8/pretext/shared-probe-plane.npz"],
            "selected_full_transition": selected,
            "restart_contract": ["M8/restart-contract.json"],
        },
        "arm_checkpoint_payloads": {arm: {
            role: (arm_final if role in {"best", "final"}
                   else arm_checkpoint)
            for role in ("initial", "pointwise", "best", "final")}
            for arm in ("C0", "C1", "L0", "L1", "M1")},
        "path_payloads": {name: policy for name in paths},
        "objective_payloads": objective_payloads,
        "timing_receipt_location": "timing/",
        "payload_sha256": {name: _sha(raw) for name, raw in sorted(payloads.items())
                           if name.startswith("M8/")},
    }
    manifest["receipt_sha256"] = _sha(_canonical(manifest))
    payloads["M8/manifest.json"] = _canonical(manifest)
    return payloads


class StagePersistenceTest(unittest.TestCase):
    def setUp(self):
        self.parent = Path(tempfile.mkdtemp(prefix="held_resume_", dir=C.CACHE_ROOT))

    def tearDown(self):
        if self.parent.exists():
            for path in sorted(self.parent.rglob("*"), reverse=True):
                try: path.chmod(0o755 if path.is_dir() else 0o644)
                except FileNotFoundError: pass
            shutil.rmtree(self.parent)

    def test_winner_independent_evidence_is_immutable_and_exact(self):
        store = StageBoundaryStore(self.parent / "boundaries")
        payloads = {
            "screen.json": _json(
                "entry-v2-e1-screen-evidence-v1", status="HOLM_SELECTED_NONE"
            ),
            "paired-observations.npz": _npz(
                real=np.asarray([1.0, 2.0]), twin=np.asarray([0.0, 0.5])
            ),
        }
        evidence_sha = store.publish_evidence("E1", payloads)
        loaded = store.load_evidence("E1", expected_sha256=evidence_sha)
        self.assertEqual(dict(loaded.payloads), payloads)
        self.assertEqual(store.publish_evidence("E1", payloads), evidence_sha)
        with self.assertRaisesRegex(StagePersistenceRefusal, "aggregate hash"):
            store.load_evidence("E1", expected_sha256="f" * 64)
        with self.assertRaisesRegex(StagePersistenceRefusal, "aggregate hash|differs"):
            store.publish_evidence("E1", {**payloads, "screen.json": b"different"})

        manifest = json.loads(
            (store.evidence_path("E1") / "evidence.json").read_text()
        )
        blob = store.evidence_path("E1") / manifest["payloads"][0]["file"]
        blob.chmod(0o644); blob.write_bytes(b"corrupt"); blob.chmod(0o444)
        with self.assertRaisesRegex(StagePersistenceRefusal, "content changed"):
            store.load_evidence("E1")

    def test_acceptance_census_is_strict_and_accepted_only_has_no_held_engine(self):
        store = StageBoundaryStore(self.parent / "acceptance-boundaries")
        payloads = _acceptance_m8_payloads()
        digest = store.publish_evidence("ACCEPTANCE", payloads)
        loaded = store.load_evidence("ACCEPTANCE", expected_sha256=digest)
        self.assertEqual(set(loaded.payloads), set(payloads))
        resumed = store.resume_engine(
            expected_acceptance_sha256="a" * 64,
            expected_diagnostic_evidence_sha256=digest,
        )
        self.assertIsNone(resumed.engine)
        self.assertIsNone(resumed.restored_through)
        self.assertEqual(dict(resumed.numerical), {})
        altered = dict(payloads)
        manifest = json.loads(altered["M8/manifest.json"])
        manifest["twin_objective_ids"] = manifest["twin_objective_ids"][:-1]
        core = dict(manifest); core.pop("receipt_sha256")
        manifest["receipt_sha256"] = _sha(_canonical(core))
        altered["M8/manifest.json"] = _canonical(manifest)
        other = StageBoundaryStore(self.parent / "bad-acceptance")
        with self.assertRaisesRegex(StagePersistenceRefusal, "44\\+44 census"):
            other.publish_evidence("ACCEPTANCE", altered)

    def test_crash_after_each_boundary_resumes_without_refit_or_reselection(self):
        acceptance = "a" * 64
        store = StageBoundaryStore(self.parent / "boundaries")
        runtime = CrashResumableHeldStageEngine(
            ExactHeldStageEngine(self.parent / "live-0"), store
        )
        screens = _screens()
        expected_e1 = execute_e1_screen(screens)
        e1_numerical = _e1_numerical(expected_e1)
        with self.assertRaisesRegex(InjectedBoundaryCrash, "E1"):
            runtime.execute_e1(acceptance, screens, e1_numerical,
                               crash_after_boundary=True)
        engine, numerical = store.resume_engine(expected_acceptance_sha256=acceptance)
        self.assertEqual(engine.e1.finalists, ("C01P01",))
        self.assertEqual(set(numerical["E1"].payloads), set(e1_numerical.payloads))

        payloads = _winner_payloads(); confirmation = _confirmation(payloads)
        confirmations = _confirmation_matrix(confirmation)
        objective_freeze_receipt = "5" * 64
        runtime = CrashResumableHeldStageEngine(engine, store)
        e1_boundary = store.load("E1")
        with self.assertRaisesRegex(InjectedBoundaryCrash, "E2"):
            runtime.execute_e2(
                acceptance, e1_boundary.execution.result_artifact_sha256,
                confirmations, objective_freeze_receipt,
                _e2_numerical(payloads, confirmation, objective_freeze_receipt),
                crash_after_boundary=True,
            )
        engine, numerical = store.resume_engine(expected_acceptance_sha256=acceptance)
        self.assertEqual(engine.e2.confirmation.arm, "M1")
        self.assertEqual(numerical["E2"].payload_sha256["mapper.json"],
                         _sha(payloads["mapper.json"]))

        selection = dict(engine.e2.selection_hashes)
        fold = _fold_result("E3", days_per_asset=10)
        for name in (
            "arm_score_arrays", "arm_entry_scores", "arm_arrivals",
            "arm_thresholds", "arm_evaluations", "arm_policies",
        ):
            values = getattr(fold, name)
            setattr(fold, name, MappingProxyType({
                ARM_FULL_PREFIX: values[ARM_FULL_PREFIX],
            }))
        fold.training = SelectedFoldTrainingReceipt.freeze(
            training_receipt_sha256=_sha("selected-E3-training"),
            normalizers_payload_sha256=_sha(payloads["normalizers.json"]),
            model_input_binding=fold.training.trace.model_input_binding,
            expanded_schema_sha256=_sha("expanded-schema"),
            expanded_transform_law_sha256=_sha("expanded-law"),
            e2_frozen_selection_sha256=_sha(_canonical(selection)),
            checkpoint_set_sha256=_sha({
                name: _sha(payloads[name]) for name in (
                    "encoder.safetensors", "head.safetensors",
                    "objective-head.safetensors",
                )
            }),
            chronological_stage_receipts_sha256=_sha("8-12-6-stage-receipts"),
            selected_horizon_schema_sha256=SELECTED_HORIZON_SCHEMA_SHA256,
            selected_horizon_target_law_sha256=
                SELECTED_HORIZON_TARGET_LAW_SHA256,
            selected_horizon_normalizer_sha256=_sha(
                "selected-horizon-normalizer"),
            selected_output_schema_sha256=_sha("selected-output-schema"),
            selected_ordinal_semantics_sha256=
                SELECTED_ORDINAL_SEMANTICS_SHA256,
        )
        receipt = dict(fold.receipt)
        policy_fit_days = (20210531, 20210930)
        policy_calibration_days = (20220314, 20220401)
        policy_selection_days = (20220428, 20220609)
        per_asset_policy_training = {
            asset: {
                "schema": "entry-v2-selected-policy-asset-fit-v1",
                "asset": asset,
                "chronology_law": SELECTED_POLICY_CHRONOLOGY_LAW,
                "optimizer_step_unit": "complete_asset_day_gradient",
                "mapper_weighting": "A013_ACTION_FIT_WEIGHTS",
                "training_rows": 64,
                "calibration_rows": 16,
                "training_candidate_sha256": _sha(f"fit-{asset}"),
                "calibration_candidate_sha256": _sha(f"calibration-{asset}"),
                "action_fit_weight_receipt_sha256": _sha(f"weight-{asset}"),
                "mapper_parameter_sha256": _sha(f"mapper-{asset}"),
                "phase_pair_manifest_sha256": None,
                "phase_pair_count": 0,
            }
            for asset in C.ASSETS
        }
        policy_training_core = {
            "schema": SELECTED_POLICY_TRAINING_SCHEMA,
            "chronology_law": SELECTED_POLICY_CHRONOLOGY_LAW,
            "action_fit_weight_law": SELECTED_ACTION_FIT_WEIGHT_LAW,
            "phase_pair_law": SELECTED_PHASE_PAIR_LAW,
            "decision_head_kind": "direct_neural",
            "asset_order": list(C.ASSETS),
            "fit_days": list(policy_fit_days),
            "calibration_days": list(policy_calibration_days),
            "selection_days": list(policy_selection_days),
            "per_asset": per_asset_policy_training,
        }
        selected_policy_training = {
            **policy_training_core,
            "sha256": C.object_sha256(policy_training_core),
        }
        receipt.update({
            "fold": "E3", "objective_sha256": selection["selected_objective_sha256"],
            "training_receipt_sha256": fold.training.training_receipt_sha256,
            "normalizer_sha256": fold.training.normalizers_payload_sha256,
            "model_input_binding": fold.training.model_input_binding.as_dict(),
            "arms": [ARM_FULL_PREFIX],
            "e2_frozen_selection_sha256": _sha(_canonical(selection)),
            "winner_adoption": {
                "legacy_full_prefix": False, "bundle_sha256": None, "arm": "M1",
                "objective_sha256": selection["selected_objective_sha256"],
                "decision_head_kind": "direct_neural",
                "target_row_manifest_sha256": "3" * 64,
                "e2_frozen_selection_sha256": _sha(_canonical(selection)),
                "target_control_sha256": "4" * 64,
            },
            "selected_policy_training": selected_policy_training,
        })
        receipt["arrays_sha256"] = CP._fold_array_hash(fold)
        receipt.pop("sha256", None)
        receipt["sha256"] = C.object_sha256(receipt)
        fold.receipt = MappingProxyType(receipt)
        fold = build_selected_winner_fold_report(
            fold,
            selected_arm="M1",
            decision_head_kind="direct_neural",
            objective_sha256=selection["selected_objective_sha256"],
            target_row_manifest_sha256="3" * 64,
            target_control_sha256="4" * 64,
            e2_frozen_selection_sha256=_sha(_canonical(selection)),
        )
        held = HeldWinnerArtifacts(
            MappingProxyType(payloads), fold, "C01P01", "direct_neural",
            lambda *args: None, "3" * 64,
        )
        runtime = CrashResumableHeldStageEngine(engine, store)
        e2_boundary = store.load("E2")
        with self.assertRaisesRegex(InjectedBoundaryCrash, "E3"):
            runtime.execute_e3(
                acceptance, e2_boundary.execution.result_artifact_sha256, held,
                crash_after_boundary=True,
            )
        restored, restored_numerical = store.resume_engine(
            expected_acceptance_sha256=acceptance, policy_factory=lambda *args: None,
        )
        self.assertEqual(restored.artifacts.primary_e3.candidate_ids, fold.candidate_ids)
        self.assertEqual(restored.artifacts.bundle_payloads["mapper.json"],
                         payloads["mapper.json"])
        self.assertEqual(set(restored_numerical), {"E1", "E2"})
        for stage in ("E1", "E2", "E3"):
            loaded = store.load(
                stage, policy_factory=(lambda *args: None) if stage == "E3" else None
            )
            self.assertTrue(loaded.execution.details["no_h2_open"])

        with self.assertRaisesRegex(StagePersistenceRefusal, "another acceptance"):
            store.resume_engine(expected_acceptance_sha256="b" * 64)

        manifest = json.loads((store.path("E2") / "boundary.json").read_text())
        mapper_row = next(row for row in manifest["blobs"]
                          if row["logical_name"] == "numerical/mapper.json")
        mapper_path = store.path("E2") / mapper_row["file"]
        mapper_path.chmod(0o644); mapper_path.write_bytes(b"corrupt"); mapper_path.chmod(0o444)
        with self.assertRaisesRegex(StagePersistenceRefusal, "content changed"):
            store.resume_engine(expected_acceptance_sha256=acceptance,
                                policy_factory=lambda *args: None)


if __name__ == "__main__":
    unittest.main()
