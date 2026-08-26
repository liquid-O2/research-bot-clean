#!/usr/bin/env python3
"""Score stored forecast term-structure flatness. Throwaway audit."""

from __future__ import annotations

import csv
import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv"
RECEIPT = REPO / ".audit/threshold-forecast-term-structure.json"
CHECK = "python3 .audit/score_forecast_term_structure.py"
SCHEMA = "QRE2THRESHOLDFCASTTERM1"
WINDOW_START = "2022-10-02"
WINDOW_END = "2024-12-31"
INTRADAY_HEADS = tuple(f"intraday_{minute}" for minute in range(30, 331, 30))
ARMS = ("catboost", "ridge")
KILL_FRACTION = 0.10
DOLLAR_STOP = {
    "source": "stored filter arithmetic",
    "HG": {"ceiling_usd": 1809, "rung_usd": 2000, "under": True},
    "NKD": {"ceiling_usd": 1073, "rung_usd": 1500, "under": True},
}


@dataclass(frozen=True, slots=True)
class HorizonGroup:
    arm: str
    outer_fold: int
    day: str
    heads: tuple[str, ...]
    variances: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.heads) != len(self.variances):
            raise ValueError(
                f"HorizonGroup heads {len(self.heads)} != variances "
                f"{len(self.variances)} for {self.arm} fold {self.outer_fold} "
                f"day {self.day}"
            )
        if len(self.heads) < 2:
            raise ValueError(
                f"HorizonGroup needs at least 2 heads, got {self.heads!r} "
                f"for {self.arm} fold {self.outer_fold} day {self.day}"
            )


@dataclass(frozen=True, slots=True)
class DroppedGroup:
    arm: str
    outer_fold: int
    day: str
    reason: str
    heads: tuple[str, ...]


def _head_minute(head: str) -> int:
    if not head.startswith("intraday_"):
        raise ValueError(f"expected intraday head, got {head!r}")
    return int(head.split("_", 1)[1])


def _cv(values: np.ndarray) -> float:
    if values.size < 2:
        raise ValueError(f"CV needs at least 2 values, got shape {values.shape}")
    if not np.isfinite(values).all():
        raise ValueError(f"CV got non-finite values {values.tolist()!r}")
    mean = float(np.mean(values))
    if mean <= 0.0:
        raise ValueError(f"CV mean must be positive, got {mean} from {values.tolist()!r}")
    return float(np.std(values, ddof=0) / mean)


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0.0:
        return None
    return float(numerator / denominator)


def _under_tenth(numerator: float, denominator: float) -> bool:
    return denominator > 0.0 and numerator < KILL_FRACTION * denominator


def _relative(path: Path) -> str:
    return str(path.relative_to(REPO))


def _catalogs(
    rows: list[tuple[str, int, str, str, float]],
) -> dict[str, tuple[str, ...]]:
    found: dict[str, set[str]] = {arm: set() for arm in ARMS}
    for arm, _fold, _day, head, _variance in rows:
        found[arm].add(head)
    catalogs: dict[str, tuple[str, ...]] = {}
    for arm in ARMS:
        heads = tuple(sorted(found[arm], key=_head_minute))
        if not heads:
            raise ValueError(f"arm {arm!r} has no join-era intraday rows")
        catalogs[arm] = heads
    return catalogs


def load_window_rows() -> tuple[list[tuple[str, int, str, str, float]], int, int]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"missing forecast TSV {SOURCE}")
    kept: list[tuple[str, int, str, str, float]] = []
    n_read = 0
    n_daily = 0
    with SOURCE.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"head", "arm", "outer_fold", "day", "forecast_variance"}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(
                f"{SOURCE} missing columns {sorted(missing)}, "
                f"got {reader.fieldnames!r}"
            )
        for raw in reader:
            n_read += 1
            day = str(raw["day"])
            if day < WINDOW_START or day > WINDOW_END:
                continue
            head = str(raw["head"])
            if head == "daily":
                n_daily += 1
                continue
            if head not in INTRADAY_HEADS:
                raise ValueError(f"unexpected head {head!r} on day {day}")
            arm = str(raw["arm"])
            if arm not in ARMS:
                raise ValueError(f"unexpected arm {arm!r} on day {day}")
            variance = float(raw["forecast_variance"])
            if not math.isfinite(variance):
                raise ValueError(
                    f"non-finite forecast_variance {raw['forecast_variance']!r} "
                    f"for {arm} {head} fold {raw['outer_fold']} day {day}"
                )
            kept.append((arm, int(raw["outer_fold"]), day, head, variance))
    return kept, n_read, n_daily


def _bucket_rows(
    rows: list[tuple[str, int, str, str, float]],
) -> tuple[
    dict[tuple[str, int, str], dict[str, float]],
    list[DroppedGroup],
]:
    buckets: dict[tuple[str, int, str], dict[str, float]] = {}
    dropped: list[DroppedGroup] = []
    bad: set[tuple[str, int, str]] = set()
    for arm, fold, day, head, variance in rows:
        key = (arm, fold, day)
        slot = buckets.setdefault(key, {})
        if head in slot:
            bad.add(key)
            continue
        slot[head] = variance
    clean: dict[tuple[str, int, str], dict[str, float]] = {}
    for key, slot in buckets.items():
        arm, fold, day = key
        heads = tuple(sorted(slot, key=_head_minute))
        if key in bad:
            dropped.append(DroppedGroup(arm, fold, day, "duplicate_head", heads))
            continue
        clean[key] = slot
    return clean, dropped


def build_groups(
    buckets: Mapping[tuple[str, int, str], Mapping[str, float]],
    catalogs: Mapping[str, tuple[str, ...]],
    prior_dropped: list[DroppedGroup],
) -> tuple[tuple[HorizonGroup, ...], tuple[DroppedGroup, ...]]:
    groups: list[HorizonGroup] = []
    dropped = list(prior_dropped)
    for (arm, fold, day), slot in sorted(buckets.items()):
        required = catalogs[arm]
        have = tuple(sorted(slot, key=_head_minute))
        if have != required:
            reason = "incomplete_catalog" if set(have) < set(required) else "head_mismatch"
            dropped.append(DroppedGroup(arm, fold, day, reason, have))
            continue
        variances = tuple(slot[head] for head in required)
        array = np.asarray(variances, np.float64)
        if float(np.mean(array)) <= 0.0:
            dropped.append(DroppedGroup(arm, fold, day, "nonpositive_mean", required))
            continue
        groups.append(
            HorizonGroup(
                arm=arm,
                outer_fold=fold,
                day=day,
                heads=required,
                variances=variances,
            )
        )
    return tuple(groups), tuple(dropped)


def build_service_groups(
    rows: list[tuple[str, int, str, str, float]],
) -> tuple[tuple[HorizonGroup, ...], tuple[DroppedGroup, ...]]:
    buckets: dict[tuple[int, str], dict[str, float]] = {}
    bad: set[tuple[int, str]] = set()
    for _arm, fold, day, head, variance in rows:
        key = (fold, day)
        slot = buckets.setdefault(key, {})
        if head in slot:
            bad.add(key)
            continue
        slot[head] = variance
    groups: list[HorizonGroup] = []
    dropped: list[DroppedGroup] = []
    for (fold, day), slot in sorted(buckets.items()):
        have = tuple(sorted(slot, key=_head_minute))
        if (fold, day) in bad:
            dropped.append(DroppedGroup("service", fold, day, "duplicate_head", have))
            continue
        if have != INTRADAY_HEADS:
            dropped.append(DroppedGroup("service", fold, day, "incomplete_11", have))
            continue
        variances = tuple(slot[head] for head in INTRADAY_HEADS)
        array = np.asarray(variances, np.float64)
        if float(np.mean(array)) <= 0.0:
            dropped.append(
                DroppedGroup("service", fold, day, "nonpositive_mean", INTRADAY_HEADS)
            )
            continue
        groups.append(
            HorizonGroup(
                arm="service",
                outer_fold=fold,
                day=day,
                heads=INTRADAY_HEADS,
                variances=variances,
            )
        )
    return tuple(groups), tuple(dropped)


def _day_vectors(
    groups: tuple[HorizonGroup, ...],
    heads: tuple[str, ...],
) -> dict[str, np.ndarray]:
    by_day: dict[str, list[np.ndarray]] = {}
    for group in groups:
        if group.heads != heads:
            raise ValueError(
                f"{group.arm} group heads {group.heads!r} != catalog {heads!r}"
            )
        by_day.setdefault(group.day, []).append(
            np.asarray(group.variances, np.float64)
        )
    collapsed: dict[str, np.ndarray] = {}
    for day, vectors in by_day.items():
        stacked = np.vstack(vectors)
        collapsed[day] = np.median(stacked, axis=0)
    return collapsed


def score_arm(
    arm: str,
    heads: tuple[str, ...],
    groups: tuple[HorizonGroup, ...],
    n_dropped: int,
) -> dict[str, object]:
    if not groups:
        raise ValueError(f"arm {arm!r} has no complete groups after catalog filter")
    within = np.asarray(
        [_cv(np.asarray(group.variances, np.float64)) for group in groups],
        np.float64,
    )
    day_vectors = _day_vectors(groups, heads)
    day_medians = np.asarray(
        [float(np.median(vector)) for vector in day_vectors.values()],
        np.float64,
    )
    between = _cv(day_medians)
    normalized = np.vstack(
        [vector / float(np.median(vector)) for vector in day_vectors.values()]
    )
    by_head = {
        head: _cv(normalized[:, index]) for index, head in enumerate(heads)
    }
    normalized_cv = float(np.median(np.asarray(list(by_head.values()), np.float64)))
    median_within = float(np.median(within))
    ratio_within_to_between = _ratio(median_within, between)
    ratio_normalized_to_within = _ratio(normalized_cv, median_within)
    return {
        "arm": arm,
        "heads": list(heads),
        "n_heads": len(heads),
        "n_groups": len(groups),
        "n_days": len(day_vectors),
        "n_dropped_groups": n_dropped,
        "median_within_day_cv": median_within,
        "p90_within_day_cv": float(np.percentile(within, 90)),
        "between_day_cv": between,
        "normalized_across_day_cv": normalized_cv,
        "normalized_across_day_cv_by_head": by_head,
        "ratio_within_to_between": ratio_within_to_between,
        "ratio_normalized_to_within": ratio_normalized_to_within,
        "kill_flat_level": _under_tenth(median_within, between),
        "kill_fixed_curve": _under_tenth(normalized_cv, median_within),
    }


def _drop_summary(dropped: tuple[DroppedGroup, ...]) -> dict[str, object]:
    by_reason: dict[str, int] = {}
    examples: list[dict[str, object]] = []
    for row in dropped:
        by_reason[row.reason] = by_reason.get(row.reason, 0) + 1
        if len(examples) < 8:
            examples.append(
                {
                    "arm": row.arm,
                    "outer_fold": row.outer_fold,
                    "day": row.day,
                    "reason": row.reason,
                    "heads": list(row.heads),
                }
            )
    return {
        "n": len(dropped),
        "by_reason": by_reason,
        "examples": examples,
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    rows, n_read, n_daily = load_window_rows()
    catalogs = _catalogs(rows)
    buckets, bucket_drops = _bucket_rows(rows)
    groups, dropped = build_groups(buckets, catalogs, bucket_drops)
    service_groups, service_dropped = build_service_groups(rows)
    n_all_11 = sum(1 for group in groups if group.heads == INTRADAY_HEADS)
    arms: dict[str, object] = {}
    for arm in ARMS:
        selected = tuple(group for group in groups if group.arm == arm)
        n_dropped = sum(1 for row in dropped if row.arm == arm)
        arms[arm] = score_arm(arm, catalogs[arm], selected, n_dropped)
    service = score_arm(
        "service",
        INTRADAY_HEADS,
        service_groups,
        len(service_dropped),
    )
    named = [arms[arm] for arm in ARMS]
    kill_flat = all(bool(block["kill_flat_level"]) for block in named)
    kill_curve = all(bool(block["kill_fixed_curve"]) for block in named)
    killed = kill_flat or kill_curve
    join_days = sorted({day for _arm, _fold, day, _head, _var in rows})
    return {
        "schema": SCHEMA,
        "status": "KILL" if killed else "OK",
        "verdict": "KILL" if killed else "SURVIVE",
        "survives": not killed,
        "kill_flat_level": kill_flat,
        "kill_fixed_curve": kill_curve,
        "wall_clock_sec": wall_clock_sec,
        "window": [WINDOW_START, WINDOW_END],
        "intraday_heads": list(INTRADAY_HEADS),
        "n_source_rows": n_read,
        "n_window_daily_rows": n_daily,
        "n_window_intraday_rows": len(rows),
        "n_join_intraday_days": len(join_days),
        "n_groups_with_all_11_per_arm": n_all_11,
        "arm_catalogs": {arm: list(heads) for arm, heads in catalogs.items()},
        "dropped_groups": _drop_summary(dropped),
        "service_dropped_groups": _drop_summary(service_dropped),
        "arms": arms,
        "service": service,
        "dollar_stop": DOLLAR_STOP if killed else None,
        "kill_bar": {
            "stated_before_scan": True,
            "fraction": KILL_FRACTION,
            "flat_level": (
                "median within-day CV under 10% of between-day CV on both arms"
            ),
            "fixed_curve": (
                "across-day CV of day-median-normalized values under 10% of "
                "within-day CV on both arms"
            ),
        },
        "definitions": {
            "within_day_cv": (
                "CV of forecast_variance across one (arm, fold, day) group's "
                "published heads"
            ),
            "between_day_cv": (
                "CV across days of the day's median after collapsing folds "
                "by per-head median"
            ),
            "ratio_within_to_between": "median_within_day_cv / between_day_cv",
            "ratio_normalized_to_within": (
                "median per-head across-day CV of day-median-normalized "
                "vectors / median_within_day_cv"
            ),
            "arm_catalog": (
                "This TSV publishes complementary heads per arm. A named-arm "
                "group is complete when it has every head that arm publishes "
                "in the window. Zero (arm, fold, day) groups have all 11 heads."
            ),
            "service": (
                "Pooled (fold, day) 11-head curve. Reported. The two-arm "
                "verdict does not use it."
            ),
        },
        "sources": {"forecasts": _relative(SOURCE)},
        "check_command": CHECK,
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _summarize(receipt: Mapping[str, object]) -> str:
    arms = receipt.get("arms", {})
    bits = []
    if isinstance(arms, dict):
        for arm in ARMS:
            block = arms.get(arm, {})
            if not isinstance(block, dict):
                continue
            bits.append(
                f"{arm}:within={block.get('median_within_day_cv')} "
                f"between={block.get('between_day_cv')} "
                f"r1={block.get('ratio_within_to_between')} "
                f"r2={block.get('ratio_normalized_to_within')}"
            )
    return (
        f"receipt={_relative(RECEIPT)} verdict={receipt.get('verdict')} "
        + " ".join(bits)
        + f" wall_clock_sec={receipt.get('wall_clock_sec')}"
    )


def main() -> int:
    started = time.perf_counter()
    receipt = build_receipt(0.0)
    receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    _write_receipt(receipt)
    print(_summarize(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
