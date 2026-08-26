from __future__ import annotations
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable
import numpy as np
from . import common as C
from .corpus_artifacts import _float, _guard_path_before_open, _int, _sha

FORECAST_SCHEMA = "QRE2FORECAST4"
EXPLICIT_FORECAST_SCHEMA = "entry-v2-explicit-forecast-test-adapter-v1"
QRE2_FORECAST_LAW_SHA256 = "6b43efa63272f370aa7fc3331446ff30cd616acf12e897aef13062fdf19b3a3b"
FORECAST_QUANTILES = ("q10", "q25", "q50", "q75", "q90")
FORECAST_SEGMENTS = ("SESSION", "TOKYO", "LONDON", "NY")
PHASE_FORECAST_SEGMENT = MappingProxyType({0: "TOKYO", 1: "LONDON", 2: "NY"})
FORECAST_SCOPE_FIELDS = (
    "forecast_age_sec",
    "sigma_hat_usd",
    "range_hat_usd",
    "sigma_components_present",
    "sigma_raw_hat_usd",
    "sigma_persistence_usd",
    "sigma_calibration_ratio",
    "sigma_calibration_count",
    "sigma_calibrated_hat_usd",
    "sigma_shrinkage_delta_usd",
    "sigma_ols_minus_persistence_usd",
    "sigma_ols_over_persistence",
    *(f"move_{quantile}_usd" for quantile in FORECAST_QUANTILES),
    "rv5_over_rv66",
    "rv5_over_rv66_present",
    "regime_low_present",
    "regime_mid_present",
    "regime_high_present",
    "regime_present",
    "move_ladder_present",
    "unscaled_fallback_present",
    "forecast_present",
    "vintage_history_present",
    "vintage_ready_count_5",
    "vintage_ready_count_22",
    "vintage_sigma_delta_1_usd",
    "vintage_sigma_slope_5_usd",
    "vintage_sigma_slope_22_usd",
    "vintage_sigma_acceleration_usd",
    "vintage_range_delta_1_usd",
    "vintage_range_slope_5_usd",
    "vintage_range_slope_22_usd",
    "vintage_range_acceleration_usd",
    "vintage_q50_delta_1_usd",
    "vintage_q50_slope_5_usd",
    "vintage_q50_slope_22_usd",
    "vintage_q50_acceleration_usd",
    "vintage_q90_delta_1_usd",
    "vintage_q90_slope_5_usd",
    "vintage_q90_slope_22_usd",
    "vintage_q90_acceleration_usd",
    "vintage_rv_ratio_delta_1",
    "vintage_rv_ratio_slope_5",
    "vintage_rv_ratio_slope_22",
    "vintage_rv_ratio_acceleration",
    "vintage_regime_changed",
    "vintage_regime_persistence",
)
FORECAST_FEATURE_FIELDS = tuple((f"{scope}_{name}" for scope in ("session", "phase") for name in FORECAST_SCOPE_FIELDS))


@dataclass(frozen=True, slots=True)
class ForecastQuery:
    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    phase: int


@dataclass(frozen=True, slots=True)
class ForecastSegmentSnapshot:
    segment: str
    status: str
    availability_ts_ns: int
    sigma_hat_usd: float | None
    range_hat_usd: float | None
    move_usd: tuple[float | None, ...]
    rv5_over_rv66: float | None
    regime: str
    ladder_source: str
    lineage_sha256: str
    sigma_raw_hat_usd: float | None = None
    sigma_persistence_usd: float | None = None
    sigma_calibration_ratio: float | None = None
    n_sigma_calibration: int | None = None

    def validate(self, *, expected_segment: str, decision_ts_ns: int) -> None:
        if self.segment != expected_segment or self.segment not in FORECAST_SEGMENTS:
            raise C.EntryV2Refusal("forecast segment/candidate phase mismatch")
        if not 0 < int(self.availability_ts_ns) < int(decision_ts_ns):
            raise C.EntryV2Refusal("forecast availability is not strictly prior")
        if len(self.move_usd) != len(FORECAST_QUANTILES):
            raise C.EntryV2Refusal("forecast move ladder width mismatch")
        _sha(self.lineage_sha256, "forecast row lineage")
        if self.status == "MISSING":
            if self.sigma_hat_usd is not None or self.range_hat_usd is not None or self.sigma_raw_hat_usd is not None or (self.sigma_persistence_usd is not None) or (self.sigma_calibration_ratio is not None) or (self.n_sigma_calibration is not None) or (self.rv5_over_rv66 is not None) or any((value is not None for value in self.move_usd)) or (self.regime != "NA") or (self.ladder_source != "MISSING"):
                raise C.EntryV2Refusal("MISSING forecast segment carries student values")
            return
        if self.status != "READY":
            raise C.EntryV2Refusal("forecast segment has an unknown status")
        if self.ladder_source not in {"MISSING", "REGIME", "UNSCALED_FALLBACK"}:
            raise C.EntryV2Refusal("READY forecast segment has an invalid ladder source")
        if self.regime not in {"NA", "LOW", "MID", "HIGH"}:
            raise C.EntryV2Refusal("READY forecast segment has an invalid regime")
        required = (self.sigma_hat_usd, self.range_hat_usd)
        if any((value is None or not math.isfinite(float(value)) for value in required)) or float(self.sigma_hat_usd) <= 0.0 or float(self.range_hat_usd) <= 0.0:
            raise C.EntryV2Refusal("READY forecast segment has invalid numeric values")
        components = (self.sigma_raw_hat_usd, self.sigma_persistence_usd, self.sigma_calibration_ratio)
        if any((value is not None for value in components)):
            if any((value is None or not math.isfinite(float(value)) or float(value) <= 0.0 for value in components)) or self.n_sigma_calibration is None or (not 0 <= int(self.n_sigma_calibration) <= 66):
                raise C.EntryV2Refusal("forecast sigma components are invalid")
        if self.ladder_source == "MISSING":
            if any((value is not None for value in self.move_usd)):
                raise C.EntryV2Refusal("missing forecast ladder carries move values")
        elif any((value is None or not math.isfinite(float(value)) for value in self.move_usd)):
            raise C.EntryV2Refusal("present forecast ladder has invalid move values")
        if self.rv5_over_rv66 is not None and (not math.isfinite(float(self.rv5_over_rv66))):
            raise C.EntryV2Refusal("forecast regime ratio is non-finite")


@dataclass(frozen=True, slots=True)
class ForecastRow:
    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    phase: int
    session: ForecastSegmentSnapshot
    phase_segment: ForecastSegmentSnapshot
    source_sha256: str

    def validate(self, query: ForecastQuery) -> None:
        if (self.candidate_id, self.asset, int(self.trading_day), int(self.decision_ts_ns), int(self.phase)) != (query.candidate_id, query.asset, query.trading_day, query.decision_ts_ns, query.phase):
            raise C.EntryV2Refusal("forecast row/candidate identity mismatch")
        C.guard_date(int(self.trading_day))
        if self.phase not in PHASE_FORECAST_SEGMENT:
            raise C.EntryV2Refusal("forecast query has an invalid candidate phase")
        self.session.validate(expected_segment="SESSION", decision_ts_ns=self.decision_ts_ns)
        self.phase_segment.validate(expected_segment=PHASE_FORECAST_SEGMENT[self.phase], decision_ts_ns=self.decision_ts_ns)
        _sha(self.source_sha256, "forecast source")


@runtime_checkable
class ForecastProvider(Protocol):
    receipt_sha256: str
    assets: frozenset[str]

    def forecast(self, query: ForecastQuery) -> ForecastRow | None: ...

    def session_regime(self, asset: str, trading_day: int) -> ForecastSegmentSnapshot | None: ...

    def forecast_history(self, asset: str, trading_day: int, segment: str, decision_ts_ns: int, limit: int) -> tuple[ForecastSegmentSnapshot, ...]: ...


@dataclass(frozen=True, slots=True)
class AssetScopedForecastProvider:
    delegate: ForecastProvider
    asset: str

    def __post_init__(self) -> None:
        if not isinstance(self.delegate, ForecastProvider):
            raise C.EntryV2Refusal("asset-scoped forecast delegate is invalid")
        asset = str(self.asset).upper()
        if asset not in C.ASSETS or asset not in self.delegate.assets:
            raise C.EntryV2Refusal("asset-scoped forecast asset is unavailable")
        object.__setattr__(self, "asset", asset)
        _sha(self.delegate.receipt_sha256, "forecast receipt")

    @property
    def receipt_sha256(self) -> str:
        return self.delegate.receipt_sha256

    @property
    def assets(self) -> frozenset[str]:
        return frozenset((self.asset,))

    def forecast(self, query: ForecastQuery) -> ForecastRow | None:
        if query.asset != self.asset:
            raise C.EntryV2Refusal("forecast query escaped its asset lane")
        return self.delegate.forecast(query)

    def session_regime(self, asset: str, trading_day: int) -> ForecastSegmentSnapshot | None:
        if str(asset).upper() != self.asset:
            raise C.EntryV2Refusal("forecast regime query escaped its asset lane")
        return self.delegate.session_regime(asset, trading_day)

    def forecast_history(self, asset: str, trading_day: int, segment: str, decision_ts_ns: int, limit: int) -> tuple[ForecastSegmentSnapshot, ...]:
        if str(asset).upper() != self.asset:
            raise C.EntryV2Refusal("forecast history query escaped its asset lane")
        return self.delegate.forecast_history(asset, trading_day, segment, decision_ts_ns, limit)


def _is_test_forecast_provider(provider: ForecastProvider) -> bool:
    if isinstance(provider, ExplicitForecastRows):
        return True
    if isinstance(provider, AssetScopedForecastProvider):
        return _is_test_forecast_provider(provider.delegate)
    return False


@dataclass(frozen=True, slots=True)
class ExplicitForecastRows:
    rows: tuple[ForecastRow, ...]
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        by_id: dict[str, ForecastRow] = {}
        for row in self.rows:
            if not row.candidate_id or row.candidate_id in by_id:
                raise C.EntryV2Refusal("duplicate/empty explicit forecast candidate_id")
            by_id[row.candidate_id] = row
        payload = {"schema": EXPLICIT_FORECAST_SCHEMA, "feature_fields": list(FORECAST_FEATURE_FIELDS), "rows": [{"candidate_id": row.candidate_id, "asset": row.asset, "trading_day": row.trading_day, "decision_ts_ns": row.decision_ts_ns, "phase": row.phase, "session": _forecast_snapshot_payload(row.session), "phase_segment": _forecast_snapshot_payload(row.phase_segment), "source_sha256": row.source_sha256} for row in sorted(self.rows, key=lambda item: item.candidate_id)]}
        computed = C.object_sha256(payload)
        if self.receipt_sha256 and self.receipt_sha256 != computed:
            raise C.EntryV2Refusal("explicit forecast receipt mismatch")
        object.__setattr__(self, "receipt_sha256", computed)

    def forecast(self, query: ForecastQuery) -> ForecastRow | None:
        return next((row for row in self.rows if row.candidate_id == query.candidate_id), None)

    def session_regime(self, asset: str, trading_day: int) -> ForecastSegmentSnapshot | None:
        rows = {row.session for row in self.rows if row.asset == asset and row.trading_day == int(trading_day)}
        if len(rows) > 1:
            raise C.EntryV2Refusal("explicit forecasts disagree on the asset-day session regime")
        return next(iter(rows), None)

    def forecast_history(self, asset: str, trading_day: int, segment: str, decision_ts_ns: int, limit: int) -> tuple[ForecastSegmentSnapshot, ...]:
        if segment not in FORECAST_SEGMENTS or limit < 1:
            raise C.EntryV2Refusal("explicit forecast history query is invalid")
        by_day: dict[int, ForecastSegmentSnapshot] = {}
        for row in self.rows:
            if row.asset != asset or int(row.trading_day) >= int(trading_day):
                continue
            snapshot = row.session if segment == "SESSION" else row.phase_segment if row.phase_segment.segment == segment else None
            if snapshot is not None and int(snapshot.availability_ts_ns) < int(decision_ts_ns):
                prior = by_day.get(int(row.trading_day))
                if prior is not None and prior != snapshot:
                    raise C.EntryV2Refusal("explicit forecast history disagrees within an asset-day")
                by_day[int(row.trading_day)] = snapshot
        return tuple((by_day[day] for day in sorted(by_day)[-int(limit) :]))

    @property
    def assets(self) -> frozenset[str]:
        return frozenset((row.asset for row in self.rows))


def _forecast_snapshot_payload(row: ForecastSegmentSnapshot) -> dict[str, Any]:
    return {"segment": row.segment, "status": row.status, "availability_ts_ns": row.availability_ts_ns, "sigma_hat_usd": row.sigma_hat_usd, "sigma_raw_hat_usd": row.sigma_raw_hat_usd, "sigma_persistence_usd": row.sigma_persistence_usd, "sigma_calibration_ratio": row.sigma_calibration_ratio, "n_sigma_calibration": row.n_sigma_calibration, "range_hat_usd": row.range_hat_usd, "move_usd": list(row.move_usd), "rv5_over_rv66": row.rv5_over_rv66, "regime": row.regime, "ladder_source": row.ladder_source, "lineage_sha256": row.lineage_sha256}


def _forecast_vintage_features(current: ForecastSegmentSnapshot, history: Sequence[ForecastSegmentSnapshot]) -> dict[str, float]:
    records = tuple(history) + (current,)
    ready = tuple((snapshot.status == "READY" for snapshot in records))
    output: dict[str, float] = {"vintage_history_present": float(bool(history)), "vintage_ready_count_5": float(sum(ready[-5:])), "vintage_ready_count_22": float(sum(ready[-22:]))}

    def metric(snapshot: ForecastSegmentSnapshot, name: str) -> float | None:
        if snapshot.status != "READY":
            return None
        if name == "sigma":
            value = snapshot.sigma_hat_usd
        elif name == "range":
            value = snapshot.range_hat_usd
        elif name == "q50":
            value = snapshot.move_usd[2]
        elif name == "q90":
            value = snapshot.move_usd[4]
        elif name == "rv_ratio":
            value = snapshot.rv5_over_rv66
        else:  # pragma: no cover - fixed local roster
            raise AssertionError(name)
        if value is None or not math.isfinite(float(value)):
            return None
        return float(value)

    def slope(values: Sequence[float], window: int) -> float:
        selected = np.asarray(values[-window:], np.float64)
        if len(selected) < 2:
            return 0.0
        x = np.arange(len(selected), dtype=np.float64)
        centered = x - float(x.mean())
        denominator = float(np.dot(centered, centered))
        return float(np.dot(centered, selected - selected.mean()) / denominator if denominator > 0.0 else 0.0)

    for name, unit in (("sigma", "_usd"), ("range", "_usd"), ("q50", "_usd"), ("q90", "_usd"), ("rv_ratio", "")):
        observed = [value for snapshot in records if (value := metric(snapshot, name)) is not None]
        current_value = metric(current, name)
        prior = [value for snapshot in history if (value := metric(snapshot, name)) is not None]
        delta = current_value - prior[-1] if current_value is not None and prior else 0.0
        acceleration = current_value - 2.0 * prior[-1] + prior[-2] if current_value is not None and len(prior) >= 2 else 0.0
        stem = f"vintage_{name}"
        output.update({stem + f"_delta_1{unit}": float(delta), stem + f"_slope_5{unit}": slope(observed, 5), stem + f"_slope_22{unit}": slope(observed, 22), stem + f"_acceleration{unit}": float(acceleration)})
    previous_regime = next((snapshot.regime for snapshot in reversed(history) if snapshot.status == "READY" and snapshot.regime != "NA"), None)
    current_regime = current.regime if current.status == "READY" else "NA"
    persistence = 0
    if current_regime != "NA":
        persistence = 1
        for snapshot in reversed(history):
            if snapshot.status != "READY" or snapshot.regime != current_regime:
                break
            persistence += 1
    output.update({"vintage_regime_changed": float(previous_regime is not None and current_regime != "NA" and (previous_regime != current_regime)), "vintage_regime_persistence": float(persistence)})
    return output


def _forecast_features(provider: ForecastProvider, query: ForecastQuery) -> tuple[dict[str, float], str]:
    receipt = _sha(getattr(provider, "receipt_sha256", ""), "forecast receipt")
    row = provider.forecast(query)
    if row is None:
        raise C.EntryV2Refusal(f"forecast row missing: {query.candidate_id}")
    row.validate(query)
    out: dict[str, float] = {}
    history_lineage: dict[str, tuple[str, ...]] = {}
    for scope, snapshot in (("session", row.session), ("phase", row.phase_segment)):
        present = snapshot.status == "READY"
        ladder_present = present and snapshot.ladder_source != "MISSING"
        ratio_present = present and snapshot.rv5_over_rv66 is not None
        regime_present = present and snapshot.regime != "NA"
        values = {
            "forecast_age_sec": (query.decision_ts_ns - snapshot.availability_ts_ns) / 1000000000.0 if present else 0.0,
            "sigma_hat_usd": float(snapshot.sigma_hat_usd) if present else 0.0,
            "range_hat_usd": float(snapshot.range_hat_usd) if present else 0.0,
            "sigma_components_present": float(present and snapshot.sigma_raw_hat_usd is not None),
            "sigma_raw_hat_usd": float(snapshot.sigma_raw_hat_usd) if present and snapshot.sigma_raw_hat_usd is not None else 0.0,
            "sigma_persistence_usd": float(snapshot.sigma_persistence_usd) if present and snapshot.sigma_persistence_usd is not None else 0.0,
            "sigma_calibration_ratio": float(snapshot.sigma_calibration_ratio) if present and snapshot.sigma_calibration_ratio is not None else 0.0,
            "sigma_calibration_count": float(snapshot.n_sigma_calibration) if present and snapshot.n_sigma_calibration is not None else 0.0,
            "sigma_calibrated_hat_usd": float(snapshot.sigma_raw_hat_usd) * float(snapshot.sigma_calibration_ratio) if present and snapshot.sigma_raw_hat_usd is not None and (snapshot.sigma_calibration_ratio is not None) else 0.0,
            "sigma_shrinkage_delta_usd": float(snapshot.sigma_hat_usd) - float(snapshot.sigma_raw_hat_usd) if present and snapshot.sigma_raw_hat_usd is not None else 0.0,
            "sigma_ols_minus_persistence_usd": float(snapshot.sigma_raw_hat_usd) - float(snapshot.sigma_persistence_usd) if present and snapshot.sigma_raw_hat_usd is not None and (snapshot.sigma_persistence_usd is not None) else 0.0,
            "sigma_ols_over_persistence": float(snapshot.sigma_raw_hat_usd) / float(snapshot.sigma_persistence_usd) if present and snapshot.sigma_raw_hat_usd is not None and (snapshot.sigma_persistence_usd is not None) and (float(snapshot.sigma_persistence_usd) > 0.0) else 0.0,
            **{f"move_{quantile}_usd": float(value) if ladder_present else 0.0 for quantile, value in zip(FORECAST_QUANTILES, snapshot.move_usd)},
            "rv5_over_rv66": float(snapshot.rv5_over_rv66) if ratio_present else 0.0,
            "rv5_over_rv66_present": float(ratio_present),
            "regime_low_present": float(regime_present and snapshot.regime == "LOW"),
            "regime_mid_present": float(regime_present and snapshot.regime == "MID"),
            "regime_high_present": float(regime_present and snapshot.regime == "HIGH"),
            "regime_present": float(regime_present),
            "move_ladder_present": float(ladder_present),
            "unscaled_fallback_present": float(present and snapshot.ladder_source == "UNSCALED_FALLBACK"),
            "forecast_present": float(present),
        }
        history = provider.forecast_history(query.asset, query.trading_day, snapshot.segment, query.decision_ts_ns, 22)
        if any((int(item.availability_ts_ns) >= int(query.decision_ts_ns) for item in history)):
            raise C.EntryV2Refusal("forecast history is not strictly prior")
        values.update(_forecast_vintage_features(snapshot, history))
        history_lineage[scope] = tuple((item.lineage_sha256 for item in history))
        for name in FORECAST_SCOPE_FIELDS:
            out[f"{scope}_{name}"] = values[name]
    row_lineage = C.object_sha256({"schema": "entry-v2-candidate-forecast-join-v2", "provider_receipt_sha256": receipt, "candidate_id": row.candidate_id, "asset": row.asset, "trading_day": row.trading_day, "decision_ts_ns": row.decision_ts_ns, "phase": row.phase, "feature_fields": list(FORECAST_FEATURE_FIELDS), "feature_values": [out[name] for name in FORECAST_FEATURE_FIELDS], "session": _forecast_snapshot_payload(row.session), "phase_segment": _forecast_snapshot_payload(row.phase_segment), "history_lineage": history_lineage, "source_sha256": row.source_sha256})
    return (out, row_lineage)


@dataclass(frozen=True, slots=True)
class QRE2ForecastArtifactInput:
    root: Path
    asset: str
    artifact_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        root = Path(self.root)
        _guard_path_before_open(root)
        object.__setattr__(self, "root", root)
        asset = str(self.asset).upper()
        if asset not in C.ASSETS:
            raise C.EntryV2Refusal("unsupported QRE2 forecast asset")
        object.__setattr__(self, "asset", asset)
        _sha(self.artifact_sha256, "forecast artifact")
        _sha(self.receipt_sha256, "forecast receipt")


class QRE2ForecastProvider:
    """Verified production reader for C++ QRE2FORECAST4 artifacts."""

    def __init__(self, inputs: Sequence[QRE2ForecastArtifactInput]) -> None:
        if not inputs:
            raise C.EntryV2Refusal("QRE2 forecast artifacts cannot be empty")
        assets = [item.asset for item in inputs]
        if len(assets) != len(set(assets)):
            raise C.EntryV2Refusal("duplicate QRE2 forecast artifact asset")
        rows: dict[tuple[str, int, str], ForecastSegmentSnapshot] = {}
        pins: list[dict[str, str]] = []
        for item in sorted(inputs, key=lambda value: value.asset):
            from .corpus_forecast_qre2 import _read_qre2_forecast

            parsed, law_sha = _read_qre2_forecast(item)
            for key, value in parsed.items():
                if key in rows:
                    raise C.EntryV2Refusal("duplicate QRE2 forecast row key")
                rows[key] = value
            pins.append({"asset": item.asset, "artifact_sha256": item.artifact_sha256, "receipt_sha256": item.receipt_sha256, "law_sha256": law_sha})
        self._rows = MappingProxyType(rows)
        history: dict[tuple[str, str], tuple[tuple[int, ForecastSegmentSnapshot], ...]] = {}
        for asset in assets:
            for segment in FORECAST_SEGMENTS:
                history[asset, segment] = tuple(sorted(((day, snapshot) for (row_asset, day, row_segment), snapshot in rows.items() if row_asset == asset and row_segment == segment), key=lambda item: item[0]))
        self._history = MappingProxyType(history)
        self._artifacts = MappingProxyType({item.asset: item.artifact_sha256 for item in inputs})
        self.assets = frozenset(assets)
        self.receipt_sha256 = C.object_sha256({"schema": "entry-v2-qre2-forecast-provider-v4", "artifacts": pins})

    def forecast(self, query: ForecastQuery) -> ForecastRow | None:
        phase_name = PHASE_FORECAST_SEGMENT.get(int(query.phase))
        if phase_name is None:
            raise C.EntryV2Refusal("forecast query has an invalid phase")
        session = self._rows.get((query.asset, query.trading_day, "SESSION"))
        phase = self._rows.get((query.asset, query.trading_day, phase_name))
        if session is None or phase is None:
            return None
        artifact_sha = self._artifacts.get(query.asset)
        if artifact_sha is None:
            return None
        return ForecastRow(query.candidate_id, query.asset, query.trading_day, query.decision_ts_ns, query.phase, session, phase, artifact_sha)

    def session_regime(self, asset: str, trading_day: int) -> ForecastSegmentSnapshot | None:
        return self._rows.get((str(asset).upper(), int(trading_day), "SESSION"))

    def forecast_history(self, asset: str, trading_day: int, segment: str, decision_ts_ns: int, limit: int) -> tuple[ForecastSegmentSnapshot, ...]:
        asset = str(asset).upper()
        if asset not in self.assets or segment not in FORECAST_SEGMENTS or int(limit) < 1:
            raise C.EntryV2Refusal("QRE2 forecast history query is invalid")
        selected = [snapshot for day, snapshot in self._history[asset, segment] if int(day) < int(trading_day) and int(snapshot.availability_ts_ns) < int(decision_ts_ns)]
        return tuple(selected[-int(limit) :])


def _forecast_optional(row: Mapping[str, str], name: str) -> float | None:
    return _float(row, name, optional=True)


def _forecast_lineage(row: Mapping[str, str], law_sha256: str) -> str:
    segment_index = {name: index for index, name in enumerate(FORECAST_SEGMENTS)}
    status_index = {"READY": 0, "MISSING": 1}
    reason_index = {"NONE": 0, "DESIGN_HISTORY": 1, "MIN_TRAIN": 2, "RANK_DEFICIENT": 3, "NONFINITE_PREDICTION": 4}
    regime_index = {"NA": 0, "LOW": 1, "MID": 2, "HIGH": 3}
    ladder_index = {"MISSING": 0, "REGIME": 1, "UNSCALED_FALLBACK": 2}
    try:
        enums = (segment_index[row["segment"]], status_index[row["status"]], reason_index[row["missing_reason"]], regime_index[row["regime_tag"]], ladder_index[row["ladder_source"]])
    except KeyError as exc:
        raise C.EntryV2Refusal("unknown QRE2 forecast enum") from exc
    asset_index = C.ASSET_INDEX.get(row.get("asset", ""))
    if asset_index is None:
        raise C.EntryV2Refusal("unknown QRE2 forecast asset")
    int_fields = ("d8", "history_end_d8", "availability_ts_ns", "fit_month", "fit_end_range_d8", "fit_end_sigma_d8", "n_train_range", "rank_range", "n_train_sigma", "rank_sigma", "n_sigma_calibration", "n_calibration", "n_regime_calibration")
    for name in int_fields:
        value = _int(row, name)
        if row[name] != str(value):
            raise C.EntryV2Refusal(f"non-canonical QRE2 forecast integer: {name}")
    pre_sigma_float_fields = ("rv1_usd", "rv5_usd", "rv22_usd", "prior_parkinson_usd", "prior_gk_usd", "prior_rs_usd", "prior_jump_usd", "sigma_raw_hat_usd", "sigma_persistence_usd", "sigma_calibration_ratio")
    post_sigma_float_fields = ("sigma_hat_usd", "range_hat_usd", "rv5_over_rv66", "regime_cut_lo", "regime_cut_hi")
    move_ratio_fields = tuple((f"move_{q}_ratio" for q in FORECAST_QUANTILES))
    move_usd_fields = tuple((f"move_{q}_usd" for q in FORECAST_QUANTILES))
    regime_ratio_fields = tuple((f"move_rs_{q}_ratio" for q in FORECAST_QUANTILES))
    regime_usd_fields = tuple((f"move_rs_{q}_usd" for q in FORECAST_QUANTILES))
    float_fields = pre_sigma_float_fields + post_sigma_float_fields + move_ratio_fields + move_usd_fields + regime_ratio_fields + regime_usd_fields
    for name in float_fields:
        _forecast_optional(row, name)
    cpp = lambda name: "nan" if row[name] == "NA" else row[name]
    parts = [
        "QRE2FORECASTROW4",
        law_sha256,
        str(asset_index),
        row["d8"],
        str(enums[0]),
        str(enums[1]),
        str(enums[2]),
        row["history_end_d8"],
        row["availability_ts_ns"],
        row["fit_month"],
        row["fit_end_range_d8"],
        row["fit_end_sigma_d8"],
        row["n_train_range"],
        row["rank_range"],
        row["n_train_sigma"],
        row["rank_sigma"],
        *(cpp(name) for name in pre_sigma_float_fields),
        row["n_sigma_calibration"],
        *(cpp(name) for name in post_sigma_float_fields),
        str(enums[3]),
        str(enums[4]),
        row["n_calibration"],
        row["n_regime_calibration"],
        *(cpp(name) for name in move_ratio_fields),
        *(cpp(name) for name in move_usd_fields),
        *(cpp(name) for name in regime_ratio_fields),
        *(cpp(name) for name in regime_usd_fields),
        row["phase_profile_sha256"],
        row["model_sha256"],
        row["history_source_sha256"],
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
