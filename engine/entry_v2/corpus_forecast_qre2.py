"""QRE2FORECAST4 artifact parser."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re

from . import common as C
from .corpus_artifacts import _int, _read_pinned, _sha
from .corpus_forecast import (
    FORECAST_QUANTILES,
    FORECAST_SEGMENTS,
    QRE2_FORECAST_LAW_SHA256,
    ForecastSegmentSnapshot,
    QRE2ForecastArtifactInput,
    _forecast_lineage,
    _forecast_optional,
)

_FORECAST_COLUMNS = (
    "asset",
    "d8",
    "segment",
    "status",
    "missing_reason",
    "history_end_d8",
    "availability_ts_ns",
    "fit_month",
    "fit_end_range_d8",
    "fit_end_sigma_d8",
    "n_train_range",
    "rank_range",
    "n_train_sigma",
    "rank_sigma",
    "rv1_usd",
    "rv5_usd",
    "rv22_usd",
    "prior_parkinson_usd",
    "prior_gk_usd",
    "prior_rs_usd",
    "prior_jump_usd",
    "sigma_raw_hat_usd",
    "sigma_persistence_usd",
    "sigma_calibration_ratio",
    "n_sigma_calibration",
    "sigma_hat_usd",
    "range_hat_usd",
    "rv5_over_rv66",
    "regime_cut_lo",
    "regime_cut_hi",
    "regime_tag",
    "ladder_source",
    "n_calibration",
    "n_regime_calibration",
    *(name for quantile in FORECAST_QUANTILES for name in (f"move_{quantile}_ratio", f"move_{quantile}_usd")),
    *(name for quantile in FORECAST_QUANTILES for name in (f"move_rs_{quantile}_ratio", f"move_rs_{quantile}_usd")),
    "phase_profile_sha256",
    "model_sha256",
    "history_source_sha256",
    "lineage_sha256",
)


def _read_qre2_forecast(
    item: QRE2ForecastArtifactInput,
) -> tuple[dict[tuple[str, int, str], ForecastSegmentSnapshot], str]:
    artifact_path = item.root / "forecast" / f"{item.asset}.qrf4.tsv"
    receipt_path = item.root / "forecast" / f"{item.asset}.qrf4.json"
    artifact_raw = _read_pinned(artifact_path, item.artifact_sha256, f"{item.asset} QRE2 forecast artifact")
    receipt_raw = _read_pinned(receipt_path, item.receipt_sha256, f"{item.asset} QRE2 forecast receipt")
    try:
        text = artifact_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise C.EntryV2Refusal("QRE2 forecast artifact is not UTF-8") from exc
    lines = text.splitlines()
    header = re.fullmatch(
        r"# QRE2FORECAST4 start_d8=(\d{8}) end_d8_exclusive=(\d{8}) " r"asset=(SI|HG|NKD) law_sha256=([0-9a-f]{64})",
        lines[0] if lines else "",
    )
    if len(lines) < 2 or header is None or header.group(3) != item.asset:
        raise C.EntryV2Refusal("QRE2 forecast header mismatch")
    start_d8, end_d8 = int(header.group(1)), int(header.group(2))
    law_sha = _sha(header.group(4), "forecast law")
    if law_sha != QRE2_FORECAST_LAW_SHA256:
        raise C.EntryV2Refusal("QRE2 forecast model-law hash mismatch")
    C.guard_decode_window(start_d8, end_d8)
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])), delimiter="\t")
    if tuple(reader.fieldnames or ()) != _FORECAST_COLUMNS:
        raise C.EntryV2Refusal("QRE2 forecast column schema mismatch")
    raw_rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in raw_rows):
        raise C.EntryV2Refusal("QRE2 forecast row width mismatch")

    try:
        receipt = json.loads(receipt_raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("invalid QRE2 forecast receipt JSON") from exc
    if not isinstance(receipt, dict) or (
        receipt.get("schema"),
        receipt.get("asset"),
        receipt.get("forecast_law_sha256"),
        receipt.get("output_sha256"),
        receipt.get("holdout_start_d8"),
        receipt.get("final_exam_permit"),
    ) != ("QRE2FORECASTRECEIPT4", item.asset, law_sha, item.artifact_sha256, C.HOLDOUT_START_D8, False):
        raise C.EntryV2Refusal("QRE2 forecast receipt identity/hash mismatch")
    try:
        receipt_start = int(receipt["start_d8"])
        receipt_end = int(receipt["end_d8_exclusive"])
        receipt_rows = int(receipt["rows"])
        receipt_sessions = int(receipt["sessions"])
        receipt_ready = int(receipt["ready"])
        receipt_missing = int(receipt["missing"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("QRE2 forecast receipt counts/window invalid") from exc
    if (
        (receipt_start, receipt_end) != (start_d8, end_d8)
        or receipt_rows != len(raw_rows)
        or receipt_rows != receipt_sessions * len(FORECAST_SEGMENTS)
        or receipt_ready + receipt_missing != receipt_rows
    ):
        raise C.EntryV2Refusal("QRE2 forecast receipt denominator mismatch")
    source_hashes = receipt.get("source_hashes")
    if not isinstance(source_hashes, dict) or set(source_hashes) != {
        "event_manifest_sha256",
        "locks_sha256",
        "phase_schedule_sha256",
    }:
        raise C.EntryV2Refusal("QRE2 forecast source receipt mismatch")
    for name, value in source_hashes.items():
        _sha(value, f"forecast {name}")
    evaluation = receipt.get("evaluation")
    if (
        not isinstance(evaluation, dict)
        or evaluation.get("schema") != "QRE2FORECASTEVAL4"
        or int(evaluation.get("rows", -1)) != receipt_rows
        or not 0 <= int(evaluation.get("valid_rows", -1)) <= receipt_rows
        or evaluation.get("consumer_law")
        != ("diagnostics-only hindsight plane; live QRE2ForecastProvider " "must not open it")
    ):
        raise C.EntryV2Refusal("QRE2 forecast evaluation receipt mismatch")
    _sha(evaluation.get("output_sha256"), "forecast evaluation output")

    parsed: dict[tuple[str, int, str], ForecastSegmentSnapshot] = {}
    lineage: list[str] = []
    ready_count = 0
    missing_count = 0
    prior_key: tuple[int, int] | None = None
    for raw in raw_rows:
        if raw["asset"] != item.asset:
            raise C.EntryV2Refusal("QRE2 forecast row asset mismatch")
        d8 = _int(raw, "d8")
        C.guard_date(d8)
        if not start_d8 <= d8 < end_d8:
            raise C.EntryV2Refusal("QRE2 forecast row outside artifact window")
        try:
            segment_index = FORECAST_SEGMENTS.index(raw["segment"])
        except ValueError as exc:
            raise C.EntryV2Refusal("unknown QRE2 forecast segment") from exc
        key_order = (d8, segment_index)
        if prior_key is not None and key_order <= prior_key:
            raise C.EntryV2Refusal("QRE2 forecast rows are not strictly ordered")
        prior_key = key_order
        if _int(raw, "history_end_d8") >= d8 or _int(raw, "fit_month") != d8 // 100:
            raise C.EntryV2Refusal("QRE2 forecast history/fit clock mismatch")
        availability = _int(raw, "availability_ts_ns")
        if availability <= 0:
            raise C.EntryV2Refusal("QRE2 forecast availability is invalid")
        for hash_name in ("phase_profile_sha256", "model_sha256", "history_source_sha256", "lineage_sha256"):
            _sha(raw[hash_name], f"forecast {hash_name}")
        if _forecast_lineage(raw, law_sha) != raw["lineage_sha256"]:
            raise C.EntryV2Refusal("QRE2 forecast row lineage mismatch")

        status, reason = raw["status"], raw["missing_reason"]
        sigma = _forecast_optional(raw, "sigma_hat_usd")
        sigma_raw = _forecast_optional(raw, "sigma_raw_hat_usd")
        sigma_persistence = _forecast_optional(raw, "sigma_persistence_usd")
        sigma_calibration_ratio = _forecast_optional(raw, "sigma_calibration_ratio")
        n_sigma_calibration = _int(raw, "n_sigma_calibration")
        range_hat = _forecast_optional(raw, "range_hat_usd")
        ratio = _forecast_optional(raw, "rv5_over_rv66")
        unscaled = tuple(_forecast_optional(raw, f"move_{q}_usd") for q in FORECAST_QUANTILES)
        selected = tuple(_forecast_optional(raw, f"move_rs_{q}_usd") for q in FORECAST_QUANTILES)
        ladder, regime = raw["ladder_source"], raw["regime_tag"]
        n_calibration = _int(raw, "n_calibration")
        n_regime_calibration = _int(raw, "n_regime_calibration")
        if not 0 <= n_calibration <= 250 or not 0 <= n_regime_calibration <= n_calibration:
            raise C.EntryV2Refusal("QRE2 forecast calibration count invariant failed")
        design = tuple(
            _forecast_optional(raw, name)
            for name in (
                "rv1_usd",
                "rv5_usd",
                "rv22_usd",
                "prior_parkinson_usd",
                "prior_gk_usd",
                "prior_rs_usd",
                "prior_jump_usd",
            )
        )
        if status == "READY":
            ready_count += 1
            if (
                reason != "NONE"
                or any(value is None for value in design)
                or sigma_raw is None
                or sigma_raw <= 0.0
                or sigma_persistence is None
                or sigma_persistence <= 0.0
                or sigma_calibration_ratio is None
                or sigma_calibration_ratio <= 0.0
                or not 0 <= n_sigma_calibration <= 66
                or sigma is None
                or sigma <= 0.0
                or range_hat is None
                or range_hat <= 0.0
                or _int(raw, "n_train_range") < 250
                or _int(raw, "n_train_sigma") < 250
                or _int(raw, "rank_range") != 12
                or _int(raw, "rank_sigma") != 12
                or sigma != sigma_raw * sigma_calibration_ratio
                or ladder not in {"MISSING", "REGIME", "UNSCALED_FALLBACK"}
                or regime not in {"NA", "LOW", "MID", "HIGH"}
            ):
                raise C.EntryV2Refusal("QRE2 READY forecast invariant failed")
            if ladder == "MISSING":
                if n_calibration >= 30 or any(value is not None for value in unscaled + selected):
                    raise C.EntryV2Refusal("QRE2 missing ladder contradicts calibration or carries values")
            else:
                if n_calibration < 30 or any(value is None for value in unscaled + selected):
                    raise C.EntryV2Refusal("QRE2 present ladder lacks calibration or values")
                if ladder == "REGIME" and (regime == "NA" or n_regime_calibration < 30):
                    raise C.EntryV2Refusal("QRE2 regime ladder lacks prior calibration")
                if ladder == "UNSCALED_FALLBACK" and selected != unscaled:
                    raise C.EntryV2Refusal("QRE2 fallback ladder differs from unscaled ladder")
        elif status == "MISSING":
            missing_count += 1
            if (
                reason not in {"DESIGN_HISTORY", "MIN_TRAIN", "RANK_DEFICIENT", "NONFINITE_PREDICTION"}
                or sigma is not None
                or range_hat is not None
                or sigma_raw is not None
                or sigma_persistence is not None
                or sigma_calibration_ratio is not None
                or n_sigma_calibration != 0
                or ladder != "MISSING"
                or any(value is not None for value in unscaled + selected)
            ):
                raise C.EntryV2Refusal("QRE2 MISSING forecast invariant failed")
            # A present MISSING artifact row is valid causal provenance.  Its
            # possibly-known design/regime fields remain masked from students.
            sigma = range_hat = ratio = None
            sigma_raw = sigma_persistence = sigma_calibration_ratio = None
            n_sigma_calibration = None
            selected = (None,) * len(FORECAST_QUANTILES)
            regime = "NA"
        else:
            raise C.EntryV2Refusal("unknown QRE2 forecast status")
        snapshot = ForecastSegmentSnapshot(
            raw["segment"],
            status,
            availability,
            sigma,
            range_hat,
            selected,
            ratio,
            regime,
            ladder,
            raw["lineage_sha256"],
            sigma_raw,
            sigma_persistence,
            sigma_calibration_ratio,
            n_sigma_calibration,
        )
        parsed[(item.asset, d8, raw["segment"])] = snapshot
        lineage.append(raw["lineage_sha256"])

    if (ready_count, missing_count) != (receipt_ready, receipt_missing):
        raise C.EntryV2Refusal("QRE2 forecast READY/MISSING receipt mismatch")
    expected_lineage = hashlib.sha256(
        ("QRE2FORECASTLINEAGES4" + "".join(f"|{value}" for value in lineage)).encode()
    ).hexdigest()
    if receipt.get("lineage_aggregate_sha256") != expected_lineage:
        raise C.EntryV2Refusal("QRE2 forecast aggregate lineage mismatch")
    if len(parsed) != len(raw_rows):
        raise C.EntryV2Refusal("duplicate QRE2 forecast key")
    for index in range(0, len(raw_rows), len(FORECAST_SEGMENTS)):
        block = raw_rows[index : index + len(FORECAST_SEGMENTS)]
        if (
            len(block) != len(FORECAST_SEGMENTS)
            or tuple(row["segment"] for row in block) != FORECAST_SEGMENTS
            or len({row["d8"] for row in block}) != 1
        ):
            raise C.EntryV2Refusal("QRE2 forecast does not have four rows per lock")
    return parsed, law_sha
