#!/usr/bin/env python3
"""Kill-test one wall_probability veto on stored 2021 walked ENTERs."""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

AUDIT = Path(__file__).resolve().parent
if str(AUDIT) not in sys.path:
    sys.path.insert(0, str(AUDIT))

import score_h5_top2 as h5
import score_roster_kill as roster

RECEIPT = h5.REPO / ".audit/threshold-wall-veto-kill.json"
CHECK = "python3 .audit/score_wall_veto_kill.py"
SCHEMA = "QRE2THRESHOLDWALLVETOKILL1"
WORKERS = 14
FIELD = "wall_probability"
OPS = ("gt", "ge")
NAMED_OP = "gt"
NAMED_THRESHOLD = 0.2
EXPECTED_BLOCKS = {
    "H3": (142, 227.50),
    "H5": (31, 426.25),
    "H7": (139, -2051.25),
}


@dataclass(frozen=True, slots=True)
class WalkedEnter:
    variant: str
    opportunity_id: str
    series_id: str
    identity: roster.Identity
    commit_label_usd: float
    wall_probability: float


@dataclass(frozen=True, slots=True)
class VetoRule:
    field: str
    op: str
    threshold: float


def join_walked_walls(
    variant: str,
    trace: h5.VariantTrace,
    commits: Mapping[str, h5.CommitIdentity],
    labels: Mapping[str, h5.NameLabel],
    walls: Mapping[str, float],
) -> tuple[WalkedEnter, ...]:
    rows: list[WalkedEnter] = []
    for entry in trace.entries:
        identity = commits.get(entry.opportunity_id)
        if identity is None:
            raise h5.JoinUnavailable(
                f"{variant}.selected_opportunity_id",
                (
                    f"{variant} selected ID {entry.opportunity_id} on day "
                    f"{entry.day} is absent from stored delayed outcomes"
                ),
            )
        if (
            identity.asset != entry.asset
            or identity.day != entry.day
            or identity.phase != entry.phase
        ):
            raise h5.JoinUnavailable(
                f"{variant}.selected_opportunity_identity",
                (
                    f"{variant} trace and delayed outcome identity differ for "
                    f"{entry.opportunity_id}"
                ),
            )
        if abs(identity.label_usd - entry.trace_pnl_usd) > 1e-7:
            raise h5.JoinUnavailable(
                f"{variant}.selected_commit_label",
                (
                    f"{variant} trace label {entry.trace_pnl_usd} != delayed "
                    f"outcome {identity.label_usd} for {entry.opportunity_id}"
                ),
            )
        canonical = labels.get(identity.series_id)
        wall = walls.get(entry.opportunity_id)
        if canonical is None:
            raise h5.JoinUnavailable(
                f"{variant}.series_id",
                f"{variant} series {identity.series_id} is absent from age-180 labels",
            )
        if wall is None:
            raise h5.JoinUnavailable(
                f"{variant}.wall_probability",
                (
                    f"{variant} selected ID {entry.opportunity_id} lacks "
                    "stored arrival.score.wall_probability"
                ),
            )
        if not np.isfinite(wall):
            raise h5.JoinUnavailable(
                f"{variant}.wall_probability",
                (
                    f"{variant} selected ID {entry.opportunity_id} has "
                    f"non-finite wall_probability {wall!r}"
                ),
            )
        if (
            canonical.asset != entry.asset
            or canonical.day != entry.day
            or canonical.phase != entry.phase
        ):
            raise h5.JoinUnavailable(
                f"{variant}.series_identity",
                f"{variant} series {identity.series_id} crosses asset, day, or phase",
            )
        rows.append(
            WalkedEnter(
                variant=variant,
                opportunity_id=entry.opportunity_id,
                series_id=identity.series_id,
                identity=roster._identity(canonical.event, canonical.event_rank),
                commit_label_usd=identity.label_usd,
                wall_probability=float(wall),
            )
        )
    if len(rows) != trace.block_trades:
        raise h5.JoinUnavailable(
            f"{variant}.summary",
            f"{variant} walked join count {len(rows)} != block {trace.block_trades}",
        )
    return tuple(rows)


def verify_variant_blocks(
    traces: Mapping[str, h5.VariantTrace],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for variant, (trades, pnl_usd) in EXPECTED_BLOCKS.items():
        if variant not in traces:
            raise h5.JoinUnavailable(
                f"{variant}.block",
                f"missing stored {variant} trace block, expected {trades} / {pnl_usd}",
            )
        trace = traces[variant]
        if trace.block_trades != trades or abs(trace.block_pnl_usd - pnl_usd) > 1e-6:
            raise h5.JoinUnavailable(
                f"{variant}.block_parity",
                (
                    f"{variant} recomputed {trace.block_trades} trades and "
                    f"{trace.block_pnl_usd} USD, expected {trades} / {pnl_usd}"
                ),
            )
        result[variant] = {
            "trades": trace.block_trades,
            "pnl_usd": trace.block_pnl_usd,
        }
    return result


def _arrays(walked: Sequence[WalkedEnter]) -> tuple[np.ndarray, ...]:
    walls = np.asarray([row.wall_probability for row in walked], np.float64)
    dollars = np.asarray([row.commit_label_usd for row in walked], np.float64)
    h7 = np.asarray([row.variant == "H7" for row in walked], bool)
    top2 = np.asarray([row.identity == "top2" for row in walked], bool)
    return walls, dollars, h7, top2


def _kill_metrics(
    veto: np.ndarray,
    dollars: np.ndarray,
    h7: np.ndarray,
    top2: np.ndarray,
) -> dict[str, object]:
    pooled_usd = float(dollars[veto].sum()) if veto.any() else 0.0
    h7_usd = float(dollars[veto & h7].sum()) if np.any(veto & h7) else 0.0
    n_top2 = int(top2.sum())
    if n_top2 == 0:
        raise h5.JoinUnavailable(
            "kill_bar.population",
            "pooled walked top-2 ENTERs are empty",
        )
    kept_top2 = int(np.count_nonzero((~veto) & top2))
    keep_rate = float(kept_top2 / n_top2)
    pooled_negative = pooled_usd < 0.0
    h7_negative = h7_usd < 0.0
    keep_half = keep_rate > 0.5
    slacks = (-pooled_usd, -h7_usd, keep_rate - 0.5)
    n_passed = int(pooled_negative) + int(h7_negative) + int(keep_half)
    return {
        "pooled_vetoed_commit_label_usd": pooled_usd,
        "pooled_vetoed_net_negative": pooled_negative,
        "h7_vetoed_commit_label_usd": h7_usd,
        "h7_vetoed_net_negative": h7_negative,
        "keep_top2": roster._rate(kept_top2, n_top2),
        "keep_top2_gt_half": keep_half,
        "survives": n_passed == 3,
        "conditions_passed": n_passed,
        "slacks": slacks,
    }


def _rank_key(metrics: Mapping[str, object], rule: VetoRule) -> tuple[object, ...]:
    slacks = metrics["slacks"]
    return (
        bool(metrics["survives"]),
        int(metrics["conditions_passed"]),
        min(slacks),
        sum(slacks),
        -abs(rule.threshold - NAMED_THRESHOLD),
        rule.op == NAMED_OP,
    )


def evaluate_rule(
    walked: Sequence[WalkedEnter],
    walls: np.ndarray,
    dollars: np.ndarray,
    h7: np.ndarray,
    top2: np.ndarray,
    rule: VetoRule,
) -> dict[str, object]:
    veto = roster._vetoes(walls, rule.op, rule.threshold)
    metrics = _kill_metrics(veto, dollars, h7, top2)
    payload = {
        "field": rule.field,
        "op": rule.op,
        "threshold": float(rule.threshold),
        "survives": bool(metrics["survives"]),
        "conditions_passed": int(metrics["conditions_passed"]),
        "pooled_vetoed_commit_label_usd": metrics["pooled_vetoed_commit_label_usd"],
        "pooled_vetoed_net_negative": metrics["pooled_vetoed_net_negative"],
        "h7_vetoed_commit_label_usd": metrics["h7_vetoed_commit_label_usd"],
        "h7_vetoed_net_negative": metrics["h7_vetoed_net_negative"],
        "keep_top2": metrics["keep_top2"],
        "keep_top2_gt_half": metrics["keep_top2_gt_half"],
        "overlay": overlay(walked, veto),
    }
    return payload


def scan_rules(
    walked: Sequence[WalkedEnter],
    walls: np.ndarray,
    dollars: np.ndarray,
    h7: np.ndarray,
    top2: np.ndarray,
) -> tuple[VetoRule, dict[str, object], int, int]:
    thresholds = np.unique(walls)
    if not len(thresholds):
        raise h5.JoinUnavailable(
            "kill_bar.population",
            "pooled walked ENTERs have no wall_probability values",
        )
    best_rule: VetoRule | None = None
    best_metrics: dict[str, object] | None = None
    best_key: tuple[object, ...] | None = None
    scanned = 0
    survived = 0
    for threshold in thresholds.tolist():
        for op in OPS:
            scanned += 1
            rule = VetoRule(FIELD, op, float(threshold))
            veto = roster._vetoes(walls, op, float(threshold))
            metrics = _kill_metrics(veto, dollars, h7, top2)
            if bool(metrics["survives"]):
                survived += 1
            key = _rank_key(metrics, rule)
            if best_key is None or key > best_key:
                best_key = key
                best_rule = rule
                best_metrics = metrics
    if best_rule is None or best_metrics is None:
        raise h5.JoinUnavailable("chosen_rule", "rule scan produced no candidate")
    return best_rule, best_metrics, scanned, survived


def overlay(walked: Sequence[WalkedEnter], veto: np.ndarray) -> dict[str, object]:
    result: dict[str, object] = {}
    for variant in (*h5.VARIANTS, "pooled"):
        if variant == "pooled":
            selected = list(walked)
            mask = veto
        else:
            keep = np.asarray([row.variant == variant for row in walked], bool)
            selected = [row for row, take in zip(walked, keep.tolist()) if take]
            mask = veto[keep]
        kept = [row for row, drop in zip(selected, mask.tolist()) if not drop]
        dropped = [row for row, drop in zip(selected, mask.tolist()) if drop]
        result[variant] = {
            "kept": roster._bucket(kept),
            "vetoed": roster._bucket(dropped),
        }
    return result


def _identity_walls(
    walked: Sequence[WalkedEnter], name: roster.Identity
) -> np.ndarray:
    return np.asarray(
        [row.wall_probability for row in walked if row.identity == name],
        np.float64,
    )


def _identity_stats(values: np.ndarray) -> dict[str, object]:
    return {
        "n": int(len(values)),
        "mean": float(np.mean(values)) if len(values) else None,
    }


def separation(walked: Sequence[WalkedEnter]) -> dict[str, object]:
    top2 = _identity_walls(walked, "top2")
    losers = _identity_walls(walked, "event_not_top2")
    other = _identity_walls(walked, "non_event")
    return {
        "field": FIELD,
        "top2": _identity_stats(top2),
        "event_not_top2": _identity_stats(losers),
        "non_event": _identity_stats(other),
        "auc_top2_higher_than_event_not_top2": roster._auc_higher(top2, losers),
        "auc_top2_higher_than_non_event": roster._auc_higher(top2, other),
        "auc_event_not_top2_higher_than_non_event": roster._auc_higher(
            losers, other
        ),
    }


def _rule_payload(
    walked: Sequence[WalkedEnter],
    walls: np.ndarray,
    dollars: np.ndarray,
    h7: np.ndarray,
    top2: np.ndarray,
    rule: VetoRule,
    metrics: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if metrics is None:
        return evaluate_rule(walked, walls, dollars, h7, top2, rule)
    veto = roster._vetoes(walls, rule.op, rule.threshold)
    return {
        "field": rule.field,
        "op": rule.op,
        "threshold": float(rule.threshold),
        "survives": bool(metrics["survives"]),
        "conditions_passed": int(metrics["conditions_passed"]),
        "pooled_vetoed_commit_label_usd": metrics["pooled_vetoed_commit_label_usd"],
        "pooled_vetoed_net_negative": metrics["pooled_vetoed_net_negative"],
        "h7_vetoed_commit_label_usd": metrics["h7_vetoed_commit_label_usd"],
        "h7_vetoed_net_negative": metrics["h7_vetoed_net_negative"],
        "keep_top2": metrics["keep_top2"],
        "keep_top2_gt_half": metrics["keep_top2_gt_half"],
        "overlay": overlay(walked, veto),
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    event_receipt = h5._read_json(h5.EVENT_RECEIPT)
    oracle_receipt = h5._read_json(h5.EXTREME_RECEIPT)
    matrix = h5.load_matrix_slice()
    labels = h5.build_name_labels(matrix, oracle_receipt)
    parity = h5.verify_event_parity(matrix, labels, event_receipt, oracle_receipt)
    load_variants = list(h5.VARIANTS)
    with ThreadPoolExecutor(max_workers=min(WORKERS, 16)) as pool:
        trace_futs = {
            variant: pool.submit(h5._load_trace_entries, variant)
            for variant in load_variants
        }
        wall_futs = {
            variant: pool.submit(roster._load_walls, variant)
            for variant in load_variants
        }
        traces = {variant: trace_futs[variant].result() for variant in load_variants}
        walls = {variant: wall_futs[variant].result() for variant in load_variants}
    blocks = verify_variant_blocks(traces)
    commits = h5._load_commit_identities(traces)
    walked: list[WalkedEnter] = []
    for variant in load_variants:
        walked.extend(
            join_walked_walls(
                variant,
                traces[variant],
                commits,
                labels,
                walls[variant],
            )
        )
    wall_arr, dollars, h7, top2 = _arrays(walked)
    rule, metrics, scanned, survived = scan_rules(
        walked, wall_arr, dollars, h7, top2
    )
    named_rule = VetoRule(FIELD, NAMED_OP, NAMED_THRESHOLD)
    chosen = _rule_payload(walked, wall_arr, dollars, h7, top2, rule, metrics)
    named = _rule_payload(walked, wall_arr, dollars, h7, top2, named_rule)
    survives = bool(chosen["survives"])
    return {
        "schema": SCHEMA,
        "status": "OK" if survives else "KILL",
        "survives": survives,
        "bounds": list(h5.BOUNDS),
        "seed": h5.SEED,
        "wall_clock_sec": wall_clock_sec,
        "workers": min(WORKERS, 16),
        "promotion": "2021 cannot promote",
        "kill_bar": {
            "stated_before_scan": True,
            "field": FIELD,
            "operators": list(OPS),
            "vetoed_commit_label_usd_pooled_net_negative": True,
            "vetoed_commit_label_usd_h7_net_negative": True,
            "keep_pooled_walked_top2_gt": 0.5,
            "population": "pooled H3+H5+H7 walked ENTERs",
            "rules_scanned": scanned,
            "rules_survived": survived,
            "chosen_rank": (
                "survives, then conditions passed, then bottleneck slack, "
                "then slack sum, then closeness to 0.2, then prefer gt"
            ),
        },
        "definitions": {
            "wall_probability": (
                "arrival.score.wall_probability on the stored walked ENTER"
            ),
            "top2": (
                "Hindsight measurement label only. Fewer than two same-cell "
                "event labels strictly above this name at age 180."
            ),
            "veto": "Drop the walked ENTER when wall_probability matches the rule.",
            "named_0p2": (
                "Prior candidate wall_probability > 0.2, reported even if it loses."
            ),
            "overlay_backfill": "Ignored. Allowed only because this is a kill test.",
        },
        "sources": {
            "delayed_outcomes": h5._relative(h5.OUTCOME_CACHE),
            "component_matrix": h5._relative(h5.MATRIX),
            "component_matrix_receipt_sha256": matrix.receipt_sha256,
            "event_economics": h5._relative(h5.EVENT_RECEIPT),
            "event_oracle": h5._relative(h5.EXTREME_RECEIPT),
        },
        "event_receipt_parity": parity,
        "variant_blocks": blocks,
        "separation": separation(walked),
        "chosen_rule": chosen,
        "named_0p2": named,
        "check_command": CHECK,
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _summarize(receipt: Mapping[str, object]) -> str:
    rule = h5._mapping(receipt.get("chosen_rule", {}), "chosen_rule")
    named = h5._mapping(receipt.get("named_0p2", {}), "named_0p2")
    return (
        f"receipt={h5._relative(RECEIPT)} status={receipt.get('status')} "
        f"survives={receipt.get('survives')} "
        f"chosen={rule.get('op')}{rule.get('threshold')} "
        f"named_0p2={named.get('op')}{named.get('threshold')} "
        f"named_survives={named.get('survives')} "
        f"wall_clock_sec={receipt.get('wall_clock_sec')}"
    )


def main() -> int:
    if sys.argv[1:]:
        raise ValueError(f"unsupported arguments {sys.argv[1:]}")
    started = time.perf_counter()
    try:
        receipt = build_receipt(0.0)
        receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    except h5.JoinUnavailable as exc:
        receipt = {
            "schema": SCHEMA,
            "status": "JOIN_UNAVAILABLE",
            "survives": False,
            "missing_key": exc.missing_key,
            "detail": exc.detail,
            "bounds": list(h5.BOUNDS),
            "seed": h5.SEED,
            "wall_clock_sec": round(time.perf_counter() - started, 3),
            "check_command": CHECK,
        }
        _write_receipt(receipt)
        print(_summarize(receipt))
        return 2
    _write_receipt(receipt)
    print(_summarize(receipt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
