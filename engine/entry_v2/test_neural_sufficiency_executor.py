from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from types import SimpleNamespace
import hashlib
import unittest

import numpy as np
import torch
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

from .diagnostic_catboost import FrozenRepresentationRows
from .diagnostic_corpus import DiagnosticCorpus
from .diagnostic_inputs import ActionMaskReason, CandidateTruthBinding
from .neural_sufficiency_executor import (
    ArmRehearsalResult, DirectHeadResult, LoadedFitOnlyResources,
    RawFidelityResult, RealDataExactNeuralDiagnosticExecutor,
    RealDiagnosticExecutorRefusal,
)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _binding(candidate_id: str, asset: str, day: int, timestamp: int,
             action: bool) -> CandidateTruthBinding:
    return CandidateTruthBinding(
        candidate_id, asset, day, timestamp, 1, 0, "RTH",
        timestamp - 10, timestamp + 10, 1, 100, 102, 202, 1,
        0, 1, 1, "CLEAR", "READY", 1, 1, 0, timestamp + 1, False,
        False, True, action, True, ActionMaskReason.AVAILABLE_EXACT_TIME,
    )


class _SmallExactProvider:
    """Small numerical provider: arm results come from actual Torch fits."""

    def __init__(self) -> None:
        assets = ("HG", "NKD", "SI")
        days = (20210601, 20210615, 20210701, 20210715,
                20210802, 20210816, 20210823,
                20210901, 20210915, 20210922)
        bindings = []
        candidate, asset, day, decision, target, phase = [], [], [], [], [], []
        for ai, name in enumerate(assets):
            for i in range(88):
                cid = f"{name}-{i:03d}"; y = bool(i % 2); group = i // 2
                if group < 16: d8 = days[group % 4]
                elif group < 30: d8 = days[4 + (group - 16) % 3]
                else: d8 = days[7 + (group - 30) % 3]
                ts = 1_620_000_000_000_000_000 + ai * 10_000 + i
                bindings.append(_binding(cid, name, d8, ts, y))
                candidate.append(cid); asset.append(name); day.append(d8)
                decision.append(ts); target.append(y)
                phase.append(f"{name}-phase-{group:02d}")
        rng = np.random.default_rng(17)
        x = rng.normal(0, .02, (len(candidate), 128)).astype(np.float32)
        x[:, 0] = np.where(target, 5.0, -5.0)
        self.rows = FrozenRepresentationRows(
            x, np.asarray(candidate), np.asarray(asset), np.asarray(day, np.int64),
            np.asarray(decision, np.int64), np.asarray(target, np.int8),
            np.ones(len(candidate), bool), np.asarray(phase),
            np.full(len(candidate), "caller-label-is-ignored"), "E1",
        )
        receipt = MappingProxyType({"candidate_suffix_rows_visited": 0,
            "receipt_sha256": _digest(b"corpus"),
            "lifecycle_provenance": {
                "schema": "entry-v2-corpus-lifecycle-provenance-v1",
                "cold_or_warm": "COLD", "warm_corpus_ready": False,
                "physical_full_pack_opens": 30,
                "model_array_physical_fills": 30,
                "verified_session_durable_hits": 0,
                "verified_session_cold_publishes": 30,
                "diagnostic_plane_durable_hits": 0,
                "model_array_bytes_materialized": 1,
                "model_array_bytes_reused": 0,
                "diagnostic_plane_bytes_materialized": 1,
                "diagnostic_plane_bytes_reused": 0,
                "corpus_ready_elapsed_milestone_source":
                    "production_diagnostic_stage_return",
                "cumulative_window_identity_sha256": _digest(b"window"),
            }})
        # The executor intentionally uses only bindings/receipt for manifest
        # authority; EntryCorpus is owned by the production one-load process.
        fake_sessions = []
        open_counts = {}
        for name in assets:
            for d8 in days:
                ids = tuple(cid for cid, a, d in zip(candidate, asset, day)
                            if a == name and d == d8)
                source = SimpleNamespace(asset=name, d8=d8)
                fake_sessions.append(SimpleNamespace(candidate_ids=ids, source=source))
                open_counts[f"{name}:{d8}"] = 1
        corpus_owner = SimpleNamespace(sessions=tuple(fake_sessions))
        corpus = DiagnosticCorpus(corpus_owner, (), tuple(bindings), receipt)  # type: ignore[arg-type]
        self.loaded = LoadedFitOnlyResources(
            corpus, "one-load-small", 4, True, True, True,
            256 * 1024 ** 3, 192 * 1024 ** 3,
            True, True, True, 0, open_counts,
            {
                "schema": "entry-v2-production-resource-admission-v1",
                "session_mapping_upper_bound": 4096,
                "nofile_required": 16384,
                "nofile_soft_after": 16384,
                "vm_map_required": 65536,
                "vm_map_limit": 1048576,
                "disk_free_required_bytes": 1024 ** 4,
                "disk_free_bytes": 2 * 1024 ** 4,
                "free_inodes_required": 16384,
                "free_inodes": 1_000_000,
                "receipt_sha256": "d" * 64,
            },
            {"schema": "entry-v2-fit-only-real-corpus-preflight-v1",
             "status": "PASS", "receipt_sha256": "e" * 64},
        )

    def load_once(self):
        return self.loaded

    def fit_only_timing_provenance(self):
        lifecycle = self.loaded.corpus.receipt["lifecycle_provenance"]
        keys = (
            "schema", "cold_or_warm", "warm_corpus_ready",
            "physical_full_pack_opens", "model_array_physical_fills",
            "verified_session_durable_hits",
            "verified_session_cold_publishes",
            "diagnostic_plane_durable_hits",
            "diagnostic_plane_bytes_materialized",
            "diagnostic_plane_bytes_reused",
            "corpus_ready_elapsed_milestone_source",
            "cumulative_window_identity_sha256",
        )
        return {key: lifecycle[key] for key in keys}

    def audit_raw_fidelity(self, loaded, manifest):
        return RawFidelityResult(
            manifest.receipt_sha256, True, True, True, True, True, True, True,
            True, True, True, True, True, True, _digest(b"raw"),
        )

    @staticmethod
    def _torch_fit(rows, manifest, arm):
        torch.manual_seed(91)
        x = torch.from_numpy(np.asarray(rows.representation, np.float32))
        y = torch.from_numpy(np.asarray(rows.action_target, np.float32))
        model = torch.nn.Linear(x.shape[1], 1)
        optimizer = torch.optim.Adam(model.parameters(), lr=.05)
        branch_gradient = False
        for _ in range(200):
            optimizer.zero_grad(set_to_none=True)
            logits = model(x).squeeze(1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, y)
            loss.backward()
            branch_gradient |= bool(model.weight.grad is not None and model.weight.grad.abs().sum() > 0)
            optimizer.step()
            if float(loss) <= .005:
                break
        with torch.no_grad():
            probability = torch.sigmoid(model(x).squeeze(1)).numpy()
        auroc, ap, bce = [], [], []
        assets = np.asarray(rows.asset, str); truth = np.asarray(rows.action_target, int)
        for asset in ("HG", "NKD", "SI"):
            at = assets == asset
            auroc.append(roc_auc_score(truth[at], probability[at]))
            ap.append(average_precision_score(truth[at], probability[at]))
            bce.append(log_loss(truth[at], probability[at], labels=[0, 1]))
        artifact = _digest(b"".join(value.detach().numpy().tobytes()
                                    for value in model.state_dict().values()))
        return min(auroc), min(ap), max(bce), branch_gradient, artifact

    def rows_for_manifest(self, manifest):
        position = {str(candidate_id): index for index, candidate_id in enumerate(
            np.asarray(self.rows.candidate_id, str)
        )}
        indices = np.asarray([position[candidate_id]
                              for candidate_id in manifest.candidate_id], np.int64)
        return FrozenRepresentationRows(
            np.ascontiguousarray(self.rows.representation[indices], np.float32),
            np.asarray(self.rows.candidate_id)[indices],
            np.asarray(self.rows.asset)[indices],
            np.asarray(self.rows.day)[indices],
            np.asarray(self.rows.decision_ts_ns)[indices],
            np.asarray(self.rows.action_target)[indices],
            np.asarray(self.rows.action_loss_mask)[indices],
            np.asarray(self.rows.exact_time_group_id)[indices],
            np.asarray(self.rows.split)[indices],
            self.rows.chronology, self.rows.eligible_development_days,
            self.rows.group_semantics,
        )

    def train_and_rehearse_arm(self, loaded, manifest, arm):
        rows = self.rows_for_manifest(manifest)
        auroc, ap, bce, gradient, artifact = self._torch_fit(rows, manifest, arm)
        return ArmRehearsalResult(
            arm, manifest.receipt_sha256, _digest(b"schema"), gradient, True,
            0.0, 1.0, auroc, ap, bce, True, True, True, True, rows, artifact,
        )

    def fit_direct_head(self, loaded, manifest, representation):
        auroc, ap, bce, gradient, artifact = self._torch_fit(representation, manifest, "direct")
        return DirectHeadResult(manifest.receipt_sha256, representation, auroc, ap,
                                bce, gradient, True, artifact)

    def fit_catboost_competence(self, rows):
        from .diagnostic_catboost import rehearse_catboost_competence
        return rehearse_catboost_competence(
            rows, expected_representation_sha256=rows.representation_sha256,
            pair_rows=self.rows)


class RealExecutorTest(unittest.TestCase):
    def test_partial_durable_recovery_is_valid_cold_timing(self):
        provider = _SmallExactProvider()
        lifecycle = dict(provider.loaded.corpus.receipt["lifecycle_provenance"])
        lifecycle.update({
            "cold_or_warm": "COLD",
            "physical_full_pack_opens": 25,
            "model_array_physical_fills": 25,
            "verified_session_durable_hits": 5,
            "verified_session_cold_publishes": 25,
            "diagnostic_plane_durable_hits": 0,
            "model_array_bytes_reused": 1,
        })
        receipt = dict(provider.loaded.corpus.receipt)
        receipt["lifecycle_provenance"] = lifecycle
        corpus = DiagnosticCorpus(
            provider.loaded.corpus.corpus, provider.loaded.corpus.sessions,
            provider.loaded.corpus.bindings, MappingProxyType(receipt),
        )
        open_counts = dict(provider.loaded.source_open_count_by_session)
        for key in tuple(sorted(open_counts))[:5]:
            open_counts[key] = 0
        provider.loaded = replace(
            provider.loaded, corpus=corpus,
            source_open_count_by_session=MappingProxyType(open_counts),
        )
        executor = RealDataExactNeuralDiagnosticExecutor(provider)
        executor.prepare()
        self.assertEqual(executor.timing_provenance()["load_class"], "cold")
        self.assertEqual(executor.timing_provenance()["lifecycle"]["cold_or_warm"],
                         "COLD")

    def test_manifest_is_derived_and_five_real_torch_rehearsals_run(self):
        provider = _SmallExactProvider(); executor = RealDataExactNeuralDiagnosticExecutor(provider)
        one_load = executor.prepare(); raw = executor.raw_fidelity()
        self.assertEqual(one_load.component, "one_load")
        self.assertTrue(raw.details["fit_only_firewall_exact"])
        for arm in ("C0", "C1", "L0", "L1", "M1"):
            evidence = executor.train_and_rehearse_arm(arm)
            self.assertLessEqual(evidence.details["maximum_bce"], .02)
        self.assertEqual(set(executor.manifest.split), {"FIT"})
        self.assertNotIn("caller-label-is-ignored", executor.manifest.split)

    def test_catboost_component_runs_real_pinned_fit_on_direct_rows(self):
        provider = _SmallExactProvider(); executor = RealDataExactNeuralDiagnosticExecutor(provider)
        executor.prepare(); executor.raw_fidelity()
        for arm in ("C0", "C1", "L0", "L1", "M1"):
            executor.train_and_rehearse_arm(arm)
        manifest = executor.manifest
        assert manifest is not None
        competence_rows = provider.rows_for_manifest(manifest)
        direct = provider.fit_direct_head(provider.loaded, manifest, competence_rows)
        executor.direct = direct
        evidence = executor.run_catboost()
        self.assertTrue(evidence.details["deterministic_cpu"])
        self.assertEqual(evidence.details["representation_sha256"],
                         competence_rows.representation_sha256)

    def test_order_and_manifest_mismatch_refuse(self):
        provider = _SmallExactProvider(); executor = RealDataExactNeuralDiagnosticExecutor(provider)
        executor.prepare()
        with self.assertRaises(RealDiagnosticExecutorRefusal):
            executor.train_and_rehearse_arm("M1")
        original = provider.audit_raw_fidelity
        provider.audit_raw_fidelity = lambda loaded, manifest: replace(  # type: ignore[method-assign]
            original(loaded, manifest), manifest_sha256="0" * 64
        )
        with self.assertRaises(RealDiagnosticExecutorRefusal):
            executor.raw_fidelity()


if __name__ == "__main__":
    unittest.main()
