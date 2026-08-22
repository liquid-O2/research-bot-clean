"""Re-gate a published policy block artifact under the CURRENT economic law.

RAIL-0 (design/RAIL0_LADDER_GATE_SPEC.md L3) bumped the gate receipt schema to
QRE2TABECONOMICGATE2, so `load_policy_block_result` now refuses every block
artifact published before the ladder with the typed "strict block replay gate
differs".  That refusal is correct -- those artifacts carry a gate computed
under superseded law -- so this tool is the ONLY sanctioned way to read an old
block under the new law: it strict-loads the artifact and its day traces
exactly as `load_policy_block_result` does, applies the current gate, and
writes `<artifact>.regate.json` beside the artifact.  It never rewrites the
artifact and never re-runs a model.

Run (SC-RAIL0-5, the two frozen E1R blocks):
  python3 tools/regate_policy_block.py <block.json> [<block.json> ...]
Self-test (no published artifacts touched):
  python3 tools/regate_policy_block.py --selftest
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Final, Mapping, Sequence
import unittest

sys.path.insert(0, "/workspace")

from engine.entry_v2 import common as C
from engine.entry_v2.tabular_calibration import (
    BlockReplayEvidence, evaluate_economic_gate,
)
from engine.entry_v2.tabular_evaluation import (
    BLOCK_RESULT_SCHEMA, _evidence_from_trace_payload, _strict_payload,
)
from engine.entry_v2.tabular_recovery_contracts import (
    RecoveryConfig, RecoveryRefusal,
)

REGATE_SCHEMA: Final = "QRE2TABREGATE1"


def regate_receipt_path(path: str | Path) -> Path:
    return Path(str(path) + ".regate.json")


def regate_receipt(*, source: Path, payload: Mapping[str, object],
                   evidence: BlockReplayEvidence,
                   config: RecoveryConfig) -> dict[str, object]:
    """Apply the current gate to already-loaded block evidence."""

    detail = payload.get("gate_detail")
    if not isinstance(detail, Mapping) or "reasons" not in detail:
        raise RecoveryRefusal("block artifact carries no published gate detail")
    gate = evaluate_economic_gate(evidence, config=config)
    core = {"schema": REGATE_SCHEMA, "artifact": str(source),
            "artifact_receipt_sha256": str(payload["receipt_sha256"]),
            "old_gate_receipt_sha256": str(payload["gate"]),
            "old_reasons": list(detail["reasons"]),
            "new_reasons": list(gate.reasons),
            "laws_pass": bool(gate.laws_pass),
            "ladder": dict(gate.ladder),
            "usd_per_trade_by_asset": dict(gate.usd_per_trade_by_asset),
            "gate_receipt_sha256": gate.receipt_sha256}
    return {**core, "receipt_sha256": C.object_sha256(core)}


def regate_artifact(path: str | Path, *, config: RecoveryConfig
                    ) -> dict[str, object]:
    """Strict-load the artifact and its traces, then re-gate them."""

    source, payload = _strict_payload(path, BLOCK_RESULT_SCHEMA)
    evidence = _evidence_from_trace_payload(payload)
    return regate_receipt(source=source, payload=payload, evidence=evidence,
                          config=config)


def write_regate_receipt(path: str | Path,
                         receipt: Mapping[str, object]) -> Path:
    target = regate_receipt_path(path)
    target.write_text(json.dumps(C.canonical_json_value(receipt), indent=2,
                                 sort_keys=True) + "\n")
    return target


def _synthetic_pre_ladder_payload(reasons: Sequence[str]
                                  ) -> dict[str, object]:
    return {"receipt_sha256": "b" * 64, "gate": "c" * 64,
            "gate_detail": {"reasons": list(reasons)}}


class RegateSelfTest(unittest.TestCase):
    """Red fixture: a tool still applying the pre-ladder law fails these."""

    def setUp(self) -> None:
        # The fixture builder is the engine's own ladder-gate test helper, so
        # the tool's selftest cannot drift from the gate's own fixtures.
        from engine.entry_v2.test_tabular_ladder_gate import _ladder_evidence
        self.evidence = _ladder_evidence(
            usd_per_asset_day=1_800.0, ceiling_usd_per_day=2_000.0,
            trades_per_asset_day=4)

    def test_regate_applies_ladder_and_drops_usd_per_trade_refusal(self):
        receipt = regate_receipt(
            source=Path("/workspace/artifacts/synthetic_block.json"),
            payload=_synthetic_pre_ladder_payload(
                ("USD_PER_TRADE:SI", "ASSET_DAY_FLOOR:SI")),
            evidence=self.evidence, config=RecoveryConfig())
        self.assertEqual(receipt["old_reasons"],
                         ["USD_PER_TRADE:SI", "ASSET_DAY_FLOOR:SI"])
        self.assertEqual(receipt["new_reasons"], [])
        self.assertTrue(receipt["laws_pass"])
        for asset in C.ASSETS:
            self.assertEqual(receipt["ladder"][asset]["rung_usd"],
                             C.LADDER_FALLBACK_ASSET_DAY_USD)
            self.assertAlmostEqual(
                receipt["usd_per_trade_by_asset"][asset], 450.0)

    def test_regate_keeps_a_failing_block_failing(self):
        from engine.entry_v2.test_tabular_ladder_gate import _ladder_evidence
        receipt = regate_receipt(
            source=Path("/workspace/artifacts/synthetic_block.json"),
            payload=_synthetic_pre_ladder_payload(("ASSET_DAY_FLOOR:SI",)),
            evidence=_ladder_evidence(usd_per_asset_day=1_300.0,
                                      ceiling_usd_per_day=1_200.0),
            config=RecoveryConfig())
        self.assertFalse(receipt["laws_pass"])
        self.assertIn("ASSET_DAY_LADDER:SI", receipt["new_reasons"])
        self.assertFalse(receipt["ladder"]["SI"]["rung_supported"])

    def test_missing_published_gate_detail_refuses(self):
        with self.assertRaises(RecoveryRefusal):
            regate_receipt(source=Path("/workspace/artifacts/x.json"),
                           payload={"receipt_sha256": "b" * 64,
                                    "gate": "c" * 64},
                           evidence=self.evidence, config=RecoveryConfig())

    def test_tampered_artifact_refuses_before_any_gate(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=C.REPO_ROOT / "artifacts") as raw:
            path = Path(raw) / "block.json"
            path.write_text(json.dumps(
                {"schema": BLOCK_RESULT_SCHEMA, "h2_open_count": 0,
                 "receipt_sha256": "d" * 64}))
            with self.assertRaises(RecoveryRefusal) as caught:
                regate_artifact(path, config=RecoveryConfig())
        self.assertEqual(str(caught.exception),
                         "evaluation artifact schema/receipt differs")

    def test_receipt_path_lands_beside_the_artifact(self):
        self.assertEqual(regate_receipt_path("/a/b/raw_block.json"),
                         Path("/a/b/raw_block.json.regate.json"))


def main(argv: Sequence[str]) -> int:
    if "--selftest" in argv:
        result = unittest.main(argv=[argv[0]], exit=False).result
        return 0 if result.wasSuccessful() else 1
    targets = [value for value in argv[1:] if not value.startswith("-")]
    if not targets:
        print(__doc__)
        return 2
    config = RecoveryConfig()
    for target in targets:
        receipt = regate_artifact(target, config=config)
        written = write_regate_receipt(target, receipt)
        print(f"{target}\n  laws_pass={receipt['laws_pass']} "
              f"reasons={receipt['new_reasons']}\n  receipt -> {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
