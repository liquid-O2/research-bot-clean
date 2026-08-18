#!/usr/bin/env python3
"""Byte-pinned authority for the Codex Entry V2 recovery plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import common as C


BASE_PLAN_SHA256 = "452ab386e0ec03fc2e4dc3942184a5374d2b0730deea288f9a480fefb144ca24"
AMENDMENTS_SHA256 = "3cec55792eec11b7c800723b9dd813ceb317fb65814e2c45149cfed61bd20c04"
NEURAL_DIAGNOSTIC_SHA256 = (
    "fd1e8c2ef0e73c9ba1ce2de09a6f3d5b2f315fe2de7ebb6dc942771ad27c5c49"
)
CLOCK_LAW_SHA256 = "dfc33cfe21c7deff5ab09d82963f1b1eff77c91d5073f2bb1aacdedfca8151f1"
CLOCK_LAW_RECEIPT_FILE_SHA256 = (
    "37c5b0e81e199193158632b3e8f61808ef82c23c71233ff9a3c75510e126f9e3"
)
BASE_PLAN_RELATIVE = Path("design/ENTRY_V2_RECOVERY_PLAN.md")
AMENDMENTS_RELATIVE = Path("design/ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md")
NEURAL_DIAGNOSTIC_RELATIVE = Path(
    "design/ENTRY_V2_NEURAL_SUFFICIENCY_DIAGNOSTIC.md"
)
CLOCK_LAW_RELATIVE = Path("design/ENTRY_V2_DATABENTO_CLOCK_LAW.md")
CLOCK_LAW_RECEIPT_RELATIVE = Path(
    "provenance/entry_v2/databento_clock_law.receipt.json"
)


@dataclass(frozen=True, slots=True)
class PlanContract:
    base_plan_sha256: str
    amendments_sha256: str
    neural_diagnostic_sha256: str
    clock_law_sha256: str
    clock_law_receipt_file_sha256: str
    minimum_asset_day_usd: float
    denominator: str
    objective: str

    def receipt(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": "entry-v2-plan-contract-v3",
            "base_plan_sha256": self.base_plan_sha256,
            "amendments_sha256": self.amendments_sha256,
            "neural_diagnostic_sha256": self.neural_diagnostic_sha256,
            "clock_law_sha256": self.clock_law_sha256,
            "clock_law_receipt_file_sha256": self.clock_law_receipt_file_sha256,
            "minimum_asset_day_usd": self.minimum_asset_day_usd,
            "denominator": self.denominator,
            "objective": self.objective,
        }
        payload["sha256"] = C.object_sha256(payload)
        return payload


def verify_plan_contract(workspace: str | Path = C.REPO_ROOT) -> PlanContract:
    root = Path(workspace).resolve()
    base = (root / BASE_PLAN_RELATIVE).resolve()
    amendments = (root / AMENDMENTS_RELATIVE).resolve()
    neural_diagnostic = (root / NEURAL_DIAGNOSTIC_RELATIVE).resolve()
    clock_law = (root / CLOCK_LAW_RELATIVE).resolve()
    clock_receipt = (root / CLOCK_LAW_RECEIPT_RELATIVE).resolve()
    if any(root not in path.parents for path in (
            base, amendments, neural_diagnostic, clock_law, clock_receipt)):
        raise C.EntryV2Refusal("entry-v2 plan path escaped workspace")
    for path, expected in (
        (base, BASE_PLAN_SHA256),
        (amendments, AMENDMENTS_SHA256),
        (neural_diagnostic, NEURAL_DIAGNOSTIC_SHA256),
        (clock_law, CLOCK_LAW_SHA256),
        (clock_receipt, CLOCK_LAW_RECEIPT_FILE_SHA256),
    ):
        if not path.is_file() or C.file_sha256(path) != expected:
            raise C.EntryV2Refusal(f"entry-v2 plan authority drifted: {path}")
    return PlanContract(
        BASE_PLAN_SHA256,
        AMENDMENTS_SHA256,
        NEURAL_DIAGNOSTIC_SHA256,
        CLOCK_LAW_SHA256,
        CLOCK_LAW_RECEIPT_FILE_SHA256,
        C.TARGET_ASSET_DAY_USD,
        "asset_trading_day",
        "maximize_full_dollars_and_clean_oracle_capture_above_floor",
    )


__all__ = [
    "AMENDMENTS_SHA256",
    "BASE_PLAN_SHA256",
    "CLOCK_LAW_SHA256",
    "CLOCK_LAW_RECEIPT_FILE_SHA256",
    "NEURAL_DIAGNOSTIC_SHA256",
    "PlanContract",
    "verify_plan_contract",
]
