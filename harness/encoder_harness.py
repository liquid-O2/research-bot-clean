#!/usr/bin/env python3
"""Standalone encoder micro-harness for the Entry V2 fix pass (design R1-R9).

The 55-minute driver cycle is the iteration killer, so every constant the fix
pass introduced is MEASURED here first, inside one live process:

  factory -> prepare (the expensive one-load, ~10 min)
  -> base stage for ONE named arm under R1/R2/F2/F3/R8/R9
  -> per-epoch governed traces, gradient shares, memory-value margin
  -> the R7 acceptance metric: HELD-DAY TOP-3 DOLLARS from memory-only probe
     scores versus the memory-OCCLUDED baseline.

R7 is the currency that matters: Q1 measured every shallow model at ~$0 or
negative per day at the top while oracle top-3 is SI $5,123 / HG $3,743 /
NKD $2,171 per held day, and geometry at AUROC 0.702 still lost $41/day.
AUROC is not the goal; top-rank dollars are.  Gate-5 (identity) and
reconstruction stay necessary floors only.

This script never gates anything.  It sets constants from measurement.

Usage:
    python3 harness/encoder_harness.py --arm M1
    python3 harness/encoder_harness.py --arm L0 --sessions 12 --epoch-ceiling 6
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_RUN_ROOT = "/workspace/artifacts/cache/port/entry_v2_runs/encoder_harness"
DEFAULT_DATA_ROOT = "/workspace/artifacts/cache/port/entry_v2"
COMPLIANT_STATUSES = ("CLEAR", "READY")
TOP_K = 3


# ---------------------------------------------------------------------------
# The acceptance currency (pre-registration sections 1, 4, 8, 9)
#
# Hindsight top-3 was a LOOKAHEAD coordinate system: the cap fills
# chronologically, so a rule that picks the day's best three after the fact
# cannot be deployed.  The measured haircut is large (SI 48.5%, HG 28.0%,
# NKD 17.7%), and it re-bases every ceiling and every margin.  Selection is
# therefore ARRIVAL-ORDER: walk the day's candidates in decision-clock order
# and take the ones whose score clears a theta frozen on the TRAIN days.
# ---------------------------------------------------------------------------
GOAL_GRADE_USD = 600.0
CURRENT_LAW = {"name": "current 3/asset + portfolio 9", "budget": 9,
               "per_asset_cap": 3}
AMENDED_LAW = {"name": "amended portfolio 9, no per-asset cap", "budget": 9,
               "per_asset_cap": None}
THETA_QUANTILE_GRID = (0.80, 0.85, 0.90, 0.925, 0.95, 0.965, 0.98, 0.99, 0.995)
THETA_TARGET_BUDGET_USE = 0.8
HINDSIGHT_K = 3


def day_dollar_ledger(data_root: str, asset: str, d8: int) -> dict[str, dict]:
    """Per-candidate certified/net dollars and goal grade for one asset-day.

    The join is the Q1/P1 reference implementation: candidates and teacher
    TSVs carry a provenance header line, so ``skiprows=1`` and a tab
    separator; only compliant rows count.
    """
    import pandas as pd
    try:
        candidates = pd.read_csv(
            f"{data_root}/g1/candidates/{asset}/{d8}.tsv", sep="\t", skiprows=1)
        teacher = pd.read_csv(
            f"{data_root}/g1/teacher/{asset}/{d8}.tsv", sep="\t", skiprows=1)
    except (OSError, ValueError):
        return {}
    if not len(candidates) or not len(teacher):
        return {}
    frozen = {str(row.candidate_id): float(row.frozen_cost_usd)
              for row in candidates.itertuples()}
    ledger: dict[str, dict] = {}
    for row in teacher.itertuples():
        candidate_id = str(row.candidate_id)
        if str(row.compliance_status) not in COMPLIANT_STATUSES:
            continue
        if candidate_id not in frozen:
            continue
        certified = float(row.cert_close_usd)
        ledger[candidate_id] = {
            "certified_usd": certified,
            "net_usd": certified - frozen[candidate_id],
            "goal_grade": int(certified >= GOAL_GRADE_USD),
        }
    return ledger


def within_session_shuffled_memories(batches, memories, *, seed):
    """Section 4: permute candidate<->memory pairing INSIDE each session.

    Zeroing asks "is the memory read at all"; shuffling asks the question the
    acceptance turns on - "does THIS candidate's memory beat a sibling's from
    the same session".
    """
    import numpy as np
    shuffled = dict(memories)
    for batch in batches:
        ids = [str(value) for value in batch.candidate_ids
               if str(value) in memories]
        if len(ids) < 2:
            continue
        digest = __import__("hashlib").sha256(
            f"{int(seed)}|{batch.asset}|{int(batch.day)}|"
            f"{batch.session_id}".encode()).digest()
        generator = np.random.default_rng(
            int.from_bytes(digest[:8], "big") % (2 ** 63))
        order = generator.permutation(len(ids))
        attempts = 0
        while bool((order == np.arange(len(ids))).all()) and attempts < 8:
            order = generator.permutation(len(ids))
            attempts += 1
        for position, source in enumerate(order):
            shuffled[ids[position]] = memories[ids[int(source)]]
    return shuffled


def memory_probe_scores(probe, memories, candidate_ids, device):
    """Probe scores from the raw memory.  The UTIL logit is the selector."""
    import torch
    stacked = torch.stack([memories[cid] for cid in candidate_ids]).to(device)
    probe = probe.to(device).eval()
    with torch.no_grad():
        util, tail, value_bin = probe(stacked)
    bins = torch.arange(value_bin.shape[1], device=value_bin.device,
                        dtype=torch.float32)
    expected_bin = (torch.softmax(value_bin.float(), dim=1) * bins).sum(1)
    return {"util": util.float().cpu().numpy(),
            "tail": tail.float().cpu().numpy(),
            "expected_value_bin": expected_bin.cpu().numpy()}


def _arrival_day_stream(index, decisions, assets):
    """One trading day's candidates in DECISION-CLOCK order."""
    return sorted(index, key=lambda row: (int(decisions[row]), str(assets[row]),
                                          int(row)))


def _run_arrival_rule(day_index, decisions, assets, nets, scores, *, budget,
                      per_asset_cap, theta=None, goal_grade=None):
    """Walk arrival order, take what clears the rule, return the day's P&L.

    ``goal_grade`` selects the ORACLE variant: a perfect classifier under the
    SAME rule, which is the only ceiling a deployable selector can be judged
    against.
    """
    taken: dict[str, int] = {}
    count = 0
    total = 0.0
    per_asset: dict[str, float] = {}
    picks = []
    for row in _arrival_day_stream(day_index, decisions, assets):
        if count >= int(budget):
            break
        asset = str(assets[row])
        if per_asset_cap is not None and taken.get(asset, 0) >= int(per_asset_cap):
            continue
        if goal_grade is not None:
            accept = bool(goal_grade[row])
        else:
            accept = bool(scores[row] >= theta)
        if not accept:
            continue
        taken[asset] = taken.get(asset, 0) + 1
        count += 1
        total += float(nets[row])
        per_asset[asset] = per_asset.get(asset, 0.0) + float(nets[row])
        picks.append(row)
    return total, per_asset, picks


def _calibrate_theta(train_days, day_rows, decisions, assets, nets, scores, *,
                     budget, per_asset_cap):
    """Freeze theta on the TRAIN days at the rule's own budget.

    Section 9 measured frozen-theta transport drift live (theta from fit days
    took zero held trades), so the harness also reports the trailing-quantile
    column; this function is the FROZEN arm of that comparison.
    """
    import numpy as np
    if not train_days:
        return None
    pool = np.concatenate([scores[day_rows[day]] for day in train_days])
    best, best_gap = None, float("inf")
    for quantile in THETA_QUANTILE_GRID:
        theta = float(np.quantile(pool, quantile))
        counts = []
        for day in train_days:
            _total, _per_asset, picks = _run_arrival_rule(
                day_rows[day], decisions, assets, nets, scores,
                budget=budget, per_asset_cap=per_asset_cap, theta=theta)
            counts.append(len(picks))
        gap = abs(float(np.mean(counts)) - budget * THETA_TARGET_BUDGET_USE)
        if gap < best_gap:
            best_gap, best = gap, theta
    return best


def _hindsight_top3(day_index, nets, scores):
    import numpy as np
    order = sorted(day_index, key=lambda row: -float(scores[row]))[:HINDSIGHT_K]
    return float(np.sum([nets[row] for row in order]))


def tail_visibility(assets, nets, goal_grade, scores, held_mask):
    """Section 8 verdict 2: is the TAIL visible inside the winners?

    Among held goal-grade candidates, AUROC of the score against
    above/below-median net.  Every shallow plane measured ~chance here; the
    encoder bet is precisely that memory beats chance.
    """
    import numpy as np
    from sklearn.metrics import roc_auc_score
    out: dict[str, float | None] = {}
    for asset in sorted(set(str(value) for value in assets)):
        rows = np.asarray([index for index in range(len(assets))
                           if held_mask[index] and str(assets[index]) == asset
                           and int(goal_grade[index]) == 1], np.int64)
        if len(rows) < 8:
            out[asset] = None
            continue
        values = np.asarray([nets[row] for row in rows], np.float64)
        median = float(np.median(values))
        labels = (values > median).astype(int)
        if not 0 < labels.sum() < len(labels):
            out[asset] = None
            continue
        out[asset] = float(roc_auc_score(
            labels, np.asarray([scores[row] for row in rows], np.float64)))
    return out


def arrival_acceptance(rows, memories, probe, *, device, data_root, held_days,
                       batches, shuffle_seed, score_key="util"):
    """The R7 acceptance metric as AMENDED: arrival-order goal-grade dollars.

    Three score planes are carried: the live memory, the WITHIN-SESSION
    SHUFFLED memory (the acceptance baseline) and zeroed memory (a weaker
    reference).  Two selection rules are reported side by side: the current
    3-per-asset law and the amended portfolio-budget law.  Hindsight top-3
    survives as a reference column only, and every rule reports the oracle on
    exactly the same days.
    """
    import numpy as np
    candidate_ids = [str(value) for value in rows.candidate_id]
    assets = [str(value) for value in rows.asset]
    days = [int(value) for value in rows.day]
    decisions = [int(value) for value in rows.decision_ts_ns]
    held = set(int(value) for value in held_days)

    ledgers: dict[tuple[str, int], dict] = {}
    nets: list[float] = []; goal_grade: list[int] = []; known: list[bool] = []
    for asset, day, candidate_id in zip(assets, days, candidate_ids):
        ledger = ledgers.setdefault(
            (asset, day), day_dollar_ledger(data_root, asset, day))
        entry = ledger.get(candidate_id)
        nets.append(0.0 if entry is None else float(entry["net_usd"]))
        goal_grade.append(0 if entry is None else int(entry["goal_grade"]))
        known.append(entry is not None)
    nets = np.asarray(nets, np.float64)
    goal_grade = np.asarray(goal_grade, np.int64)
    known = np.asarray(known, bool)

    planes = {
        "memory": memories,
        "shuffled": within_session_shuffled_memories(
            batches, memories, seed=shuffle_seed),
        "occluded": None,
    }
    scores_by_plane: dict[str, "np.ndarray"] = {}
    for name, plane in planes.items():
        if plane is None:
            import torch
            zeroed = {cid: torch.zeros_like(memories[cid])
                      for cid in candidate_ids}
            plane = zeroed
        scores_by_plane[name] = memory_probe_scores(
            probe, plane, candidate_ids, device)[score_key]

    day_rows: dict[int, "np.ndarray"] = {}
    for index, day in enumerate(days):
        if not known[index]:
            continue
        day_rows.setdefault(day, []).append(index)
    day_rows = {day: np.asarray(sorted(rows_), np.int64)
                for day, rows_ in day_rows.items()}
    train_days = sorted(day for day in day_rows if day not in held)
    held_day_list = sorted(day for day in day_rows if day in held)
    if not held_day_list:
        return {"days": 0, "rules": {}, "tail_visibility": {},
                "hindsight_reference": {}}

    result: dict[str, object] = {"days": len(held_day_list),
                                 "train_days": len(train_days),
                                 "score_key": score_key,
                                 "held_days": held_day_list}
    rules: dict[str, dict] = {}
    for law in (CURRENT_LAW, AMENDED_LAW):
        entry: dict[str, object] = {"budget": law["budget"],
                                    "per_asset_cap": law["per_asset_cap"]}
        for plane, scores in scores_by_plane.items():
            theta = _calibrate_theta(
                train_days, day_rows, decisions, assets, nets, scores,
                budget=law["budget"], per_asset_cap=law["per_asset_cap"])
            per_day = []; per_asset_days: dict[str, list] = {}
            for day in held_day_list:
                total, per_asset, picks = _run_arrival_rule(
                    day_rows[day], decisions, assets, nets, scores,
                    budget=law["budget"],
                    per_asset_cap=law["per_asset_cap"], theta=theta)
                per_day.append({"day": day, "usd": total, "picks": len(picks)})
                for asset in sorted(set(assets)):
                    per_asset_days.setdefault(asset, []).append(
                        per_asset.get(asset, 0.0))
            entry[plane] = {
                "theta": theta,
                "portfolio_usd_day": float(np.mean(
                    [row["usd"] for row in per_day])),
                "picks_day": float(np.mean([row["picks"] for row in per_day])),
                "worst_day_usd": float(np.min([row["usd"] for row in per_day])),
                "per_asset_usd_day": {asset: float(np.mean(values))
                                      for asset, values in per_asset_days.items()},
                "per_day": tuple(per_day),
            }
        oracle_days = []; oracle_per_asset: dict[str, list] = {}
        for day in held_day_list:
            total, per_asset, _picks = _run_arrival_rule(
                day_rows[day], decisions, assets, nets,
                scores_by_plane["memory"], budget=law["budget"],
                per_asset_cap=law["per_asset_cap"], goal_grade=goal_grade)
            oracle_days.append(total)
            for asset in sorted(set(assets)):
                oracle_per_asset.setdefault(asset, []).append(
                    per_asset.get(asset, 0.0))
        entry["oracle"] = {
            "portfolio_usd_day": float(np.mean(oracle_days)),
            "per_asset_usd_day": {asset: float(np.mean(values))
                                  for asset, values in oracle_per_asset.items()},
        }
        # PAIRED per held day: the sign test the protocol runs on.
        paired = [entry["memory"]["per_day"][index]["usd"]
                  - entry["shuffled"]["per_day"][index]["usd"]
                  for index in range(len(held_day_list))]
        entry["paired_margin_usd_day"] = float(np.mean(paired))
        entry["paired_positive_days"] = int(sum(1 for value in paired
                                                if value > 0))
        entry["paired_days"] = len(paired)
        entry["beats_shuffled"] = bool(entry["paired_margin_usd_day"] > 0)
        rules[law["name"]] = entry
    result["rules"] = rules

    # Reference column only (a lookahead coordinate system).
    hindsight: dict[str, float] = {}
    for plane, scores in scores_by_plane.items():
        hindsight[plane] = float(np.mean(
            [_hindsight_top3(day_rows[day], nets, scores)
             for day in held_day_list]))
    hindsight["oracle"] = float(np.mean([
        float(np.sort(nets[day_rows[day]])[-HINDSIGHT_K:].sum())
        for day in held_day_list]))
    result["hindsight_reference"] = hindsight

    held_mask = np.asarray([known[index] and days[index] in held
                            for index in range(len(days))], bool)
    result["tail_visibility"] = tail_visibility(
        assets, nets, goal_grade, scores_by_plane["memory"], held_mask)
    result["tail_visibility_shuffled"] = tail_visibility(
        assets, nets, goal_grade, scores_by_plane["shuffled"], held_mask)
    return result


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------
def print_epoch_traces(receipt) -> None:
    governed = tuple(receipt["governed_traces"])
    print(f"\nGOVERNED TRACES {governed}  (F2/R3)", flush=True)
    header = "  epoch " + " ".join(f"{name:>14}" for name in governed)
    print(header + f" {'composite':>10} {'vs_shuffled':>12}", flush=True)
    values = receipt["governed_trace_values"]
    composites = receipt["checkpoint_composite_trace"]
    margins = receipt["memory_value_margin"]
    for epoch, row in enumerate(values):
        line = f"  {epoch:5d} " + " ".join(
            f"{float(row[name]):14.6f}" for name in governed)
        print(f"{line} {float(composites[epoch]):10.6f} "
              f"{float(margins[epoch]):12.6f}", flush=True)
    print(f"  best_epoch={receipt['best_epoch']} "
          f"best_composite={float(receipt['best_composite']):.6f} "
          f"stop_reason={receipt['stop_reason']} "
          f"wall_ceiling_s={float(receipt['wall_ceiling_seconds']):.0f}",
          flush=True)
    print(f"  stale_by_trace={dict(receipt['stale_by_trace'])}", flush=True)
    print(f"  baseline_law={receipt['memory_value_baseline_law']} "
          f"(zeros kept as a reference column: "
          f"{[round(float(x), 4) for x in receipt['memory_value_occluded_margin']]})",
          flush=True)
    print(f"  probe targets={list(receipt['memory_value_targets'])} "
          f"internal_weights={dict(receipt['memory_value_internal_weights'])} "
          f"measured={receipt['memory_value_internal_weights_measured']}",
          flush=True)
    print(f"  list_coverage={[round(float(x), 3) for x in receipt['memory_value_list_coverage_trace']]} "
          f"list_skips={dict(receipt['memory_value_list_training_skips'])}",
          flush=True)


def print_gradient_shares(receipt) -> None:
    print("\nENCODER GRADIENT SHARES (F3, separate backwards, same batch)",
          flush=True)
    measurements = receipt["gradient_share_measurements"]
    if not measurements:
        print("  (none measured this run)", flush=True)
        return
    for row in measurements:
        share = row["encoder_gradient_share"]
        cosine = row["cosine_to_oracle"]
        print(f"  epoch {int(row['epoch'])}", flush=True)
        for name in sorted(share, key=lambda key: -share[key]):
            conflict = (f"  cos_to_oracle={cosine[name]:+.4f}"
                        if name in cosine else "")
            print(f"    {name:14s} share={100 * share[name]:6.2f}%"
                  f"  l1={row['encoder_gradient_l1'][name]:12.2f}{conflict}",
                  flush=True)
        internal = dict(row.get("memory_value_internal_share", {}))
        if internal:
            targets = dict(row.get("memory_value_target_shares", {}))
            print("    probe internal shares (target "
                  + " ".join(f"{k}={100 * v:.0f}%"
                             for k, v in sorted(targets.items())) + "): "
                  + " ".join(f"{k}={100 * internal[k]:.1f}%"
                             for k in sorted(internal) if k != "oracle"),
                  flush=True)
        print(f"    applied_scales={dict(row['applied_scales'])}", flush=True)


def print_identity(receipt) -> None:
    print("\nCANDIDATE IDENTITY (R1)", flush=True)
    print(f"  status={receipt['identity_status']} "
          f"validation={receipt['identity_validation']} "
          f"tau={receipt['identity_temperature']} "
          f"min_gap={receipt['identity_min_cutoff_gap_events']} "
          f"max_crop={receipt['identity_max_crop_events']}", flush=True)
    print(f"  skips={dict(receipt['identity_skips'])}", flush=True)


def print_scope(receipt) -> None:
    scope = receipt["reconstruction_target_scope"]
    window = receipt["validation_window"]
    print("\nRECONSTRUCTION TARGET SCOPE (R9) AND HELD WINDOW (4.5)", flush=True)
    print(f"  scoped_fields={scope['scoped_fields']}/{scope['total_fields']} "
          f"excluded={list(scope['excluded_fields'])}", flush=True)
    print(f"  held_days={window['trailing_days']} "
          f"(baseline {window['baseline_trailing_days']}) "
          f"rows={window['held_rows']} "
          f"meets_minimum={window['meets_minimum']}", flush=True)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def print_acceptance(acceptance) -> None:
    print("\nACCEPTANCE: ARRIVAL-ORDER GOAL-GRADE DOLLARS (sections 1/4/9)",
          flush=True)
    if not acceptance["days"]:
        print("  no held asset-day carried a compliant candidate slice",
              flush=True)
        return
    print(f"  held_days={acceptance['days']} "
          f"train_days={acceptance['train_days']} "
          f"score={acceptance['score_key']} logit", flush=True)
    for name, entry in acceptance["rules"].items():
        print(f"\n  RULE {name} (budget {entry['budget']}, "
              f"per-asset cap {entry['per_asset_cap']})", flush=True)
        for plane in ("memory", "shuffled", "occluded"):
            row = entry[plane]
            theta = ("n/a" if row["theta"] is None
                     else f"{float(row['theta']):.4f}")
            print(f"    {plane:9s} theta={theta:>8s} "
                  f"portfolio=${row['portfolio_usd_day']:8.0f}/day "
                  f"picks={row['picks_day']:.1f}/day "
                  f"worst=${row['worst_day_usd']:8.0f} "
                  + " ".join(f"{asset}=${value:.0f}" for asset, value
                             in sorted(row["per_asset_usd_day"].items())),
                  flush=True)
        oracle = entry["oracle"]
        print(f"    {'ORACLE':9s} {'':>14s} "
              f"portfolio=${oracle['portfolio_usd_day']:8.0f}/day "
              + " ".join(f"{asset}=${value:.0f}" for asset, value
                         in sorted(oracle["per_asset_usd_day"].items())),
              flush=True)
        print(f"    PAIRED memory-minus-shuffled="
              f"${entry['paired_margin_usd_day']:.0f}/day  "
              f"positive_days={entry['paired_positive_days']}"
              f"/{entry['paired_days']}  "
              f"BEATS SHUFFLED: {entry['beats_shuffled']}", flush=True)
    reference = acceptance["hindsight_reference"]
    print("\n  HINDSIGHT TOP-3 (reference only - a lookahead coordinate "
          "system): " + " ".join(f"{name}=${value:.0f}" for name, value
                                 in sorted(reference.items())), flush=True)
    print("\n  TAIL VISIBILITY (held goal-grade rows, AUROC of score vs "
          "above/below-median net)", flush=True)
    for asset in sorted(acceptance["tail_visibility"]):
        live = acceptance["tail_visibility"][asset]
        shuffled = acceptance["tail_visibility_shuffled"].get(asset)
        print(f"    {asset:>3} memory="
              + ("  n/a" if live is None else f"{live:.4f}")
              + "  shuffled="
              + ("  n/a" if shuffled is None else f"{shuffled:.4f}"),
              flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", default="M1",
                        choices=("C0", "C1", "L0", "L1", "M1"))
    parser.add_argument("--run-root", default=DEFAULT_RUN_ROOT)
    parser.add_argument("--data-root", default=DEFAULT_DATA_ROOT)
    parser.add_argument("--sessions", type=int, default=0,
                        help="truncate the session batches for a fast smoke")
    parser.add_argument("--epoch-ceiling", type=int, default=0,
                        help="override the STAGE_SPECS pointwise_dense ceiling")
    parser.add_argument("--wall-ceiling-s", type=float, default=0.0)
    parser.add_argument("--identity-temperature", type=float, default=0.0)
    parser.add_argument("--aux-recon-weight", type=float, default=0.0)
    parser.add_argument("--aux-identity-weight", type=float, default=0.0)
    parser.add_argument("--aux-memory-value-weight", type=float, default=0.0)
    parser.add_argument("--share-cap-recon", type=float, default=0.0)
    parser.add_argument("--share-cap-identity", type=float, default=0.0)
    parser.add_argument("--share-cap-memory-value", type=float, default=0.0)
    parser.add_argument("--score-key", default="util",
                        choices=("util", "tail", "expected_value_bin"))
    parser.add_argument("--list-tau", type=float, default=0.0)
    parser.add_argument("--memory-value-util-weight", type=float, default=0.0)
    parser.add_argument("--memory-value-list-weight", type=float, default=0.0)
    parser.add_argument("--memory-value-tail-weight", type=float, default=0.0)
    parser.add_argument("--json-out", default="")
    return parser


def apply_measured_constants(resources, model_module, args) -> dict[str, object]:
    """Harness-set constants (F3/R1/R3).  MEASURED values land here."""
    from types import MappingProxyType
    applied: dict[str, object] = {}
    if args.identity_temperature > 0:
        resources.IDENTITY_TEMPERATURE = float(args.identity_temperature)
        applied["IDENTITY_TEMPERATURE"] = resources.IDENTITY_TEMPERATURE
    for flag, name in (("aux_recon_weight", "AUX_RECON_WEIGHT"),
                       ("aux_identity_weight", "AUX_IDENTITY_WEIGHT"),
                       ("aux_memory_value_weight", "AUX_MEMORY_VALUE_WEIGHT")):
        value = float(getattr(args, flag))
        if value > 0:
            setattr(resources, name, value)
            applied[name] = value
            resources.AUX_WEIGHTS_MEASURED = True
    caps = dict(resources.AUX_SHARE_CAPS)
    for flag, name in (("share_cap_recon", "recon"),
                       ("share_cap_identity", "identity"),
                       ("share_cap_memory_value", "memory_value")):
        value = float(getattr(args, flag))
        if value > 0:
            caps[name] = value
    if caps != dict(resources.AUX_SHARE_CAPS):
        resources.AUX_SHARE_CAPS = MappingProxyType(caps)
        resources.AUX_SHARE_CAPS_MEASURED = True
        applied["AUX_SHARE_CAPS"] = caps
    for flag, name in (("list_tau", "MEMORY_VALUE_LIST_TAU"),
                       ("memory_value_util_weight", "MEMORY_VALUE_UTIL_WEIGHT"),
                       ("memory_value_list_weight", "MEMORY_VALUE_LIST_WEIGHT"),
                       ("memory_value_tail_weight", "MEMORY_VALUE_TAIL_WEIGHT")):
        value = float(getattr(args, flag))
        if value > 0:
            setattr(resources, name, value)
            applied[name] = value
            if name != "MEMORY_VALUE_LIST_TAU":
                resources.MEMORY_VALUE_WEIGHTS_MEASURED = True
    if args.wall_ceiling_s > 0:
        ceilings = dict(resources.ARM_WALL_CEILING_SECONDS)
        ceilings[args.arm] = float(args.wall_ceiling_s)
        resources.ARM_WALL_CEILING_SECONDS = MappingProxyType(ceilings)
        applied["ARM_WALL_CEILING_SECONDS"] = ceilings
    if args.epoch_ceiling > 0:
        specs = dict(model_module.STAGE_SPECS)
        base = specs["pointwise_dense"]
        specs["pointwise_dense"] = model_module.StageTrainingSpec(
            base.name, int(args.epoch_ceiling), base.patience,
            base.minimum_relative_improvement)
        resources._STAGE_SPECS = MappingProxyType(specs)
        applied["epoch_ceiling"] = int(args.epoch_ceiling)
    return applied


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    started = time.monotonic()
    from engine.entry_v2 import neural_sufficiency_model as model_module
    from engine.entry_v2 import neural_sufficiency_resources as resources

    applied = apply_measured_constants(resources, model_module, args)
    print(f"HARNESS arm={args.arm} applied_constants={applied}", flush=True)

    executor, context = resources.entry_v2_production_executor_factory(
        Path(args.run_root))
    print(f"factory {time.monotonic() - started:.0f}s "
          f"context={getattr(context, 'receipt_sha256', None)}", flush=True)
    executor.prepare()
    print(f"one_load {time.monotonic() - started:.0f}s", flush=True)
    provider = executor.provider
    provider._prepare(executor.manifest)
    provider._manifest = executor.manifest
    print(f"provider_prepared {time.monotonic() - started:.0f}s "
          f"sessions={len(provider.batches)}", flush=True)
    if args.sessions > 0:
        provider.batches = provider.batches[:args.sessions]
        print(f"TRUNCATED to {len(provider.batches)} session batches "
              f"(smoke run: NOT an acceptance measurement)", flush=True)

    models = provider._models()
    model = models[args.arm]
    # C1/L1 consume their control's exact encoder checkpoint, as the driver does.
    if args.arm == "C1":
        model.encoder.load_state_dict(models["C0"].encoder.state_dict(), strict=True)
    if args.arm == "L1":
        model.encoder.load_state_dict(models["L0"].encoder.state_dict(), strict=True)

    encode_started = time.monotonic()
    rows, metrics, memories, _decoder, held_days, receipt = provider._encode(
        model, args.arm)
    print(f"\nbase_stage {time.monotonic() - encode_started:.0f}s "
          f"(NONSEMANTIC wall clock)", flush=True)

    print_scope(receipt)
    print_identity(receipt)
    print_epoch_traces(receipt)
    print_gradient_shares(receipt)
    print(f"\nOPTIMIZER GROUPS (R8) {dict(receipt['optimizer_param_groups'])}",
          flush=True)

    probe = provider._memory_value_probes[args.arm]
    from engine.entry_v2.neural_sufficiency_resources import (
        MEMORY_VALUE_SHUFFLE_SEED)
    acceptance = arrival_acceptance(
        rows, memories, probe, device=provider.device,
        data_root=args.data_root, held_days=held_days,
        batches=provider.batches, shuffle_seed=MEMORY_VALUE_SHUFFLE_SEED,
        score_key=args.score_key)
    print_acceptance(acceptance)
    print(f"\nGATE-5 SANITY FLOOR joint_auroc={float(metrics[0]):.4f} "
          f"ap={float(metrics[1]):.4f} logloss={float(metrics[2]):.4f}",
          flush=True)

    if args.json_out:
        payload = {
            "arm": args.arm, "applied_constants": applied,
            "acceptance": acceptance,
            "governed_traces": list(receipt["governed_traces"]),
            "governed_trace_values": [dict(row) for row
                                      in receipt["governed_trace_values"]],
            "checkpoint_composite_trace": list(
                receipt["checkpoint_composite_trace"]),
            "memory_value_trace": list(receipt["memory_value_trace"]),
            "memory_value_shuffled_baseline": list(
                receipt["memory_value_shuffled_baseline"]),
            "memory_value_margin": list(receipt["memory_value_margin"]),
            "memory_value_occluded_baseline": list(
                receipt["memory_value_occluded_baseline"]),
            "gradient_share_measurements": [
                json.loads(json.dumps(row, default=str))
                for row in receipt["gradient_share_measurements"]],
            "stop_reason": receipt["stop_reason"],
            "best_epoch": receipt["best_epoch"],
            "identity_status": receipt["identity_status"],
            "identity_validation": receipt["identity_validation"],
        }
        Path(args.json_out).write_text(json.dumps(payload, indent=2,
                                                  sort_keys=True, default=str))
        print(f"\nwrote {args.json_out}", flush=True)
    print(f"\nHARNESS DONE {time.monotonic() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    # The one-load provider spawns worker processes; without this guard the
    # spawn re-imports the module and re-enters main().
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as error:
        print(f"HARNESS REFUSAL/{type(error).__name__}: {error}", flush=True)
        traceback.print_exc()
        raise
