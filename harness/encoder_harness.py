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
# Section 9 as ruled by the user: the portfolio budget is 12, confidence
# only, per-asset hard cap removed.  The old 3/asset law stays as a LEGACY
# reference column so the cost of the cap keeps being measured.
LEGACY_LAW = {"name": "legacy 3/asset + portfolio 9", "budget": 9,
              "per_asset_cap": 3}
AMENDED_LAW = {"name": "amended portfolio 12, no per-asset cap", "budget": 12,
               "per_asset_cap": None}
SELECTION_LAWS = (LEGACY_LAW, AMENDED_LAW)
PORTFOLIO_GOAL_USD_DAY = 7_000.0
PORTFOLIO_MINIMUM_USD_DAY = 6_000.0
THETA_QUANTILE_GRID = (0.80, 0.85, 0.90, 0.925, 0.95, 0.965, 0.98, 0.99, 0.995)
THETA_TARGET_BUDGET_USE = 0.8
TRAILING_THETA_DAYS = 5
HINDSIGHT_K = 3
SCORE_QUANTILES = (0.50, 0.90, 0.99)

# Section 4 inner development folds: forward-chained, day-blocked, strictly
# inside the fit era.  Fold k fits on the first (7 + 5k) trading days and
# scores on the NEXT 5.  Constant iteration lives here; the CONFIRM blocks
# are never touched by this script.
FOLD_ERA_START_D8 = 20210531
FOLD_ERA_END_D8 = 20210625
FOLD_WALL_D8 = 20210628
FOLD_FIT_BASE_DAYS = 7
FOLD_FIT_STEP_DAYS = 5
FOLD_SCORE_DAYS = 5
FOLDS = (1, 2, 3)


def fold_calendar(trading_days, fold: int) -> dict:
    """Exact d8 lists for one inner development fold.

    Derived from the trading days the corpus ACTUALLY carries, never from a
    nominal calendar: a fold that silently ran short would be an invisible
    change to the protocol.
    """
    if int(fold) not in FOLDS:
        raise ValueError(f"fold must be one of {FOLDS}")
    era = sorted(int(day) for day in trading_days
                 if FOLD_ERA_START_D8 <= int(day) <= FOLD_ERA_END_D8)
    # Proportional amendment (2026-08-19): the diagnostic corpus's roster is
    # sparser than the calendar (measured: 8 pre-CONFIRM days). Folds derive
    # from the days the corpus ACTUALLY carries: chained 2-day score blocks
    # carved from the era's end; fold k scores block k counting forward.
    # A fold whose blocks don't exist refuses (never silently short).
    canonical_fit = FOLD_FIT_BASE_DAYS + FOLD_FIT_STEP_DAYS * int(fold)
    if len(era) >= canonical_fit + FOLD_SCORE_DAYS:
        # The canonical law whenever THIS fold fits in the era.
        fit_count = canonical_fit
        score_len = FOLD_SCORE_DAYS
    else:
        # Proportional fallback for a sparse corpus roster (measured: the
        # diagnostic corpus carries 8 pre-CONFIRM days): chained 2-day score
        # blocks carved from the era's end. Refuses rather than running a
        # degenerate fold.
        score_len = 2
        n_folds = min(3, max(0, (len(era) - 4) // score_len))
        if n_folds < 1 or int(fold) > n_folds:
            raise ValueError(
                f"fold {fold} unavailable: era carries {len(era)} days -> "
                f"{n_folds} proportional fold(s)")
        fit_count = len(era) - score_len * (n_folds - int(fold) + 1)
        if fit_count < 4:
            raise ValueError(
                f"fold {fold} fit block would be {fit_count} days (<4)")
    needed = fit_count + score_len
    if len(era) < needed:
        raise ValueError(
            f"fold {fold} needs {needed} trading days inside "
            f"{FOLD_ERA_START_D8}-{FOLD_ERA_END_D8}; the corpus carries "
            f"{len(era)}")
    fit_days = tuple(era[:fit_count])
    score_days = tuple(era[fit_count:fit_count + score_len])
    if any(day >= FOLD_WALL_D8 for day in score_days):
        raise ValueError(
            f"fold {fold} would score on or past the CONFIRM wall "
            f"{FOLD_WALL_D8}: {score_days}")
    if set(fit_days) & set(score_days):
        raise ValueError(f"fold {fold} fit and score blocks overlap")
    return {"fold": int(fold), "fit_days": fit_days, "score_days": score_days,
            "era_days": tuple(era), "era_start": FOLD_ERA_START_D8,
            "era_end": FOLD_ERA_END_D8, "wall": FOLD_WALL_D8}


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


def rank_normalize(scores, assets, days, train_days):
    """Map each asset's scores onto its OWN train-day empirical CDF.

    Final ruling 7: the util head is both the loss's logit and the ranking
    score, so a single cross-asset theta assumes a comparability the head was
    never asked to provide.  This column answers that empirically - if raw
    scores let one asset hog the portfolio budget and rank-normalized scores
    do not, the receipt carries both the diagnosis and the fix.
    """
    import numpy as np
    scores = np.asarray(scores, np.float64)
    out = np.zeros(len(scores), np.float64)
    train = set(int(day) for day in train_days)
    for asset in sorted(set(str(value) for value in assets)):
        rows = np.asarray([index for index in range(len(scores))
                           if str(assets[index]) == asset], np.int64)
        pool = np.asarray([scores[index] for index in rows
                           if int(days[index]) in train], np.float64)
        if not len(pool):
            out[rows] = 0.5
            continue
        order = np.sort(pool)
        out[rows] = np.searchsorted(order, scores[rows], side="right") / len(order)
    return out


def score_quantiles(scores, assets, days, held_days):
    """Per-asset held score quantiles - the comparability evidence."""
    import numpy as np
    held = set(int(day) for day in held_days)
    out: dict[str, dict] = {}
    for asset in sorted(set(str(value) for value in assets)):
        values = np.asarray([scores[index] for index in range(len(scores))
                             if str(assets[index]) == asset
                             and int(days[index]) in held], np.float64)
        if not len(values):
            out[asset] = {}
            continue
        out[asset] = {f"p{int(100 * q)}": float(np.quantile(values, q))
                      for q in SCORE_QUANTILES}
    return out


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
    return total, per_asset, picks, dict(taken)


def _calibrate_theta(train_days, day_rows, decisions, assets, nets, scores, *,
                     budget, per_asset_cap):
    """Freeze theta on the TRAIN days at the rule's own budget.

    Returns (theta, quantile): the quantile is what the trailing-quantile
    column re-applies to a moving window, so the two thetas differ only in
    WHICH days they are read from.
    """
    import numpy as np
    if not train_days:
        return None, None
    pool = np.concatenate([scores[day_rows[day]] for day in train_days])
    best, best_quantile, best_gap = None, None, float("inf")
    for quantile in THETA_QUANTILE_GRID:
        theta = float(np.quantile(pool, quantile))
        counts = []
        for day in train_days:
            _total, _per_asset, picks, _taken = _run_arrival_rule(
                day_rows[day], decisions, assets, nets, scores,
                budget=budget, per_asset_cap=per_asset_cap, theta=theta)
            counts.append(len(picks))
        gap = abs(float(np.mean(counts)) - budget * THETA_TARGET_BUDGET_USE)
        if gap < best_gap:
            best_gap, best, best_quantile = gap, theta, quantile
    return best, best_quantile


def _trailing_theta(previous_days, day_rows, scores, quantile):
    """Theta from the last N SCORED days at the frozen budget-quantile.

    Section 9 measured frozen-theta transport drift live (theta from the fit
    days took zero held trades), so this column travels with the data.
    """
    import numpy as np
    window = list(previous_days)[-TRAILING_THETA_DAYS:]
    if not window or quantile is None:
        return None
    pool = np.concatenate([scores[day_rows[day]] for day in window])
    return float(np.quantile(pool, quantile))


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


def _selection_column(held_day_list, day_rows, decisions, assets, nets, scores,
                      *, budget, per_asset_cap, theta, quantile,
                      trailing=False):
    """Score every held day under one rule and one theta policy."""
    import numpy as np
    per_day = []; per_asset_days: dict[str, list] = {}
    per_asset_picks: dict[str, list] = {}
    seen: list[int] = []
    for day in held_day_list:
        day_theta = theta
        if trailing:
            day_theta = _trailing_theta(seen, day_rows, scores, quantile)
            if day_theta is None:
                day_theta = theta          # first days fall back to frozen
        seen.append(day)
        if day_theta is None:
            continue
        total, per_asset, picks, taken = _run_arrival_rule(
            day_rows[day], decisions, assets, nets, scores,
            budget=budget, per_asset_cap=per_asset_cap, theta=day_theta)
        per_day.append({"day": day, "usd": total, "picks": len(picks),
                        "theta": float(day_theta)})
        for asset in sorted(set(str(value) for value in assets)):
            per_asset_days.setdefault(asset, []).append(
                per_asset.get(asset, 0.0))
            per_asset_picks.setdefault(asset, []).append(
                float(taken.get(asset, 0)))
    if not per_day:
        return None
    return {
        "theta": theta,
        "theta_quantile": quantile,
        "portfolio_usd_day": float(np.mean([row["usd"] for row in per_day])),
        "picks_day": float(np.mean([row["picks"] for row in per_day])),
        "worst_day_usd": float(np.min([row["usd"] for row in per_day])),
        "per_asset_usd_day": {asset: float(np.mean(values))
                              for asset, values in per_asset_days.items()},
        "per_asset_picks_day": {asset: float(np.mean(values))
                                for asset, values in per_asset_picks.items()},
        # Ruling 7's budget-hogging evidence: what fraction of the portfolio
        # budget each asset actually consumed.
        "per_asset_pick_share": {
            asset: (float(np.mean(values))
                    / max(1e-9, float(np.mean(
                        [row["picks"] for row in per_day]))))
            for asset, values in per_asset_picks.items()},
        "per_day": tuple(per_day),
    }


def arrival_acceptance(rows, memories, probes, *, device, data_root,
                       held_days, batches, shuffle_seed, score_key="util",
                       train_days=None):
    """The acceptance metric: ARRIVAL-ORDER goal-grade dollars, both probes.

    Three score planes (live memory, WITHIN-SESSION SHUFFLED, zeroed), two
    selection laws (legacy 3/asset+9 and the amended portfolio 12), three
    theta policies (frozen, trailing-quantile, per-asset rank-normalized) and
    two probes.  Acceptance passes on EITHER probe; the shuffled null must
    fail BOTH.
    """
    import numpy as np
    import torch
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

    # When a fold is active the caller names its FIT days explicitly: the
    # competence population reaches past the fold era, and calibrating theta
    # on a day the fold never fit on would quietly read outside the protocol.
    allowed = (None if train_days is None
               else set(int(day) for day in train_days) | held)
    day_rows_raw: dict[int, list] = {}
    for index, day in enumerate(days):
        if not known[index]:
            continue
        if allowed is not None and int(day) not in allowed:
            continue
        day_rows_raw.setdefault(day, []).append(index)
    day_rows = {day: np.asarray(sorted(values), np.int64)
                for day, values in day_rows_raw.items()}
    train_days = sorted(day for day in day_rows if day not in held)
    held_day_list = sorted(day for day in day_rows if day in held)
    if not held_day_list:
        return {"days": 0, "probes": {}, "dual": {}, "hindsight_reference": {}}

    shuffled_memories = within_session_shuffled_memories(
        batches, memories, seed=shuffle_seed)
    zeroed = {cid: torch.zeros_like(memories[cid]) for cid in candidate_ids}

    result: dict[str, object] = {
        "days": len(held_day_list), "train_days": len(train_days),
        "score_key": score_key, "held_days": held_day_list,
        "train_day_list": train_days,
    }
    probe_results: dict[str, dict] = {}
    for kind, probe in probes.items():
        planes = {"memory": memories, "shuffled": shuffled_memories,
                  "occluded": zeroed}
        raw_scores = {name: memory_probe_scores(
            probe, plane, candidate_ids, device)[score_key]
            for name, plane in planes.items()}
        normalized = {name: rank_normalize(values, assets, days, train_days)
                      for name, values in raw_scores.items()}
        entry: dict[str, object] = {
            "score_quantiles": score_quantiles(
                raw_scores["memory"], assets, days, held_day_list),
            "rules": {},
        }
        for law in SELECTION_LAWS:
            law_entry: dict[str, object] = {
                "budget": law["budget"], "per_asset_cap": law["per_asset_cap"]}
            for plane in ("memory", "shuffled", "occluded"):
                theta, quantile = _calibrate_theta(
                    train_days, day_rows, decisions, assets, nets,
                    raw_scores[plane], budget=law["budget"],
                    per_asset_cap=law["per_asset_cap"])
                law_entry[plane] = _selection_column(
                    held_day_list, day_rows, decisions, assets, nets,
                    raw_scores[plane], budget=law["budget"],
                    per_asset_cap=law["per_asset_cap"], theta=theta,
                    quantile=quantile)
                if plane == "memory":
                    # Report-only columns, both on the SAME rule.
                    law_entry["memory_trailing_quantile"] = _selection_column(
                        held_day_list, day_rows, decisions, assets, nets,
                        raw_scores[plane], budget=law["budget"],
                        per_asset_cap=law["per_asset_cap"], theta=theta,
                        quantile=quantile, trailing=True)
                    rank_theta, rank_quantile = _calibrate_theta(
                        train_days, day_rows, decisions, assets, nets,
                        normalized[plane], budget=law["budget"],
                        per_asset_cap=law["per_asset_cap"])
                    law_entry["memory_rank_normalized"] = _selection_column(
                        held_day_list, day_rows, decisions, assets, nets,
                        normalized[plane], budget=law["budget"],
                        per_asset_cap=law["per_asset_cap"], theta=rank_theta,
                        quantile=rank_quantile)
            oracle_days = []; oracle_per_asset: dict[str, list] = {}
            for day in held_day_list:
                total, per_asset, _picks, _taken = _run_arrival_rule(
                    day_rows[day], decisions, assets, nets,
                    raw_scores["memory"], budget=law["budget"],
                    per_asset_cap=law["per_asset_cap"], goal_grade=goal_grade)
                oracle_days.append(total)
                for asset in sorted(set(assets)):
                    oracle_per_asset.setdefault(asset, []).append(
                        per_asset.get(asset, 0.0))
            law_entry["oracle"] = {
                "portfolio_usd_day": float(np.mean(oracle_days)),
                "per_asset_usd_day": {asset: float(np.mean(values))
                                      for asset, values
                                      in oracle_per_asset.items()}}
            live = law_entry["memory"]; null = law_entry["shuffled"]
            if live is not None and null is not None:
                paired = [live["per_day"][index]["usd"]
                          - null["per_day"][index]["usd"]
                          for index in range(len(live["per_day"]))]
                law_entry["paired_margin_usd_day"] = float(np.mean(paired))
                law_entry["paired_positive_days"] = int(
                    sum(1 for value in paired if value > 0))
                law_entry["paired_days"] = len(paired)
                law_entry["beats_shuffled"] = bool(np.mean(paired) > 0)
                law_entry["meets_portfolio_goal"] = bool(
                    live["portfolio_usd_day"] >= PORTFOLIO_GOAL_USD_DAY)
                law_entry["meets_portfolio_minimum"] = bool(
                    live["portfolio_usd_day"] >= PORTFOLIO_MINIMUM_USD_DAY)
            entry["rules"][law["name"]] = law_entry
        held_mask = np.asarray(
            [known[index] and days[index] in held
             and (allowed is None or int(days[index]) in allowed)
             for index in range(len(days))], bool)
        entry["tail_visibility"] = tail_visibility(
            assets, nets, goal_grade, raw_scores["memory"], held_mask)
        entry["tail_visibility_shuffled"] = tail_visibility(
            assets, nets, goal_grade, raw_scores["shuffled"], held_mask)
        entry["hindsight_reference"] = {
            name: float(np.mean([_hindsight_top3(day_rows[day], nets, values)
                                 for day in held_day_list]))
            for name, values in raw_scores.items()}
        probe_results[kind] = entry
    result["probes"] = probe_results

    # Section 4's dual-acceptance rule, evaluated on the AMENDED law.
    dual: dict[str, object] = {}
    for law in SELECTION_LAWS:
        passes: dict[str, bool] = {}
        null_passes: dict[str, bool] = {}
        for kind in probe_results:
            law_entry = probe_results[kind]["rules"][law["name"]]
            passes[kind] = bool(law_entry.get("beats_shuffled", False))
            null_column = law_entry.get("shuffled")
            # The NULL fails when the shuffled plane cannot itself clear the
            # portfolio minimum.  A null that looks acceptable means the
            # metric is not discriminating, whatever the margin says.
            null_passes[kind] = bool(
                null_column is not None
                and null_column["portfolio_usd_day"] >= PORTFOLIO_MINIMUM_USD_DAY)
        dual[law["name"]] = {
            "per_probe_beats_shuffled": passes,
            "per_probe_null_clears_minimum": null_passes,
            "accepted_either": bool(any(passes.values())),
            "null_fails_both": bool(not any(null_passes.values())),
            "accepted": bool(any(passes.values())
                             and not any(null_passes.values())),
            "portfolio_minimum_usd_day": PORTFOLIO_MINIMUM_USD_DAY,
            "portfolio_goal_usd_day": PORTFOLIO_GOAL_USD_DAY,
            "rule": "EITHER_PROBE_PASSES_SHUFFLED_NULL_FAILS_BOTH",
        }
    result["dual"] = dual
    result["hindsight_reference"] = {
        "oracle": float(np.mean([
            float(np.sort(nets[day_rows[day]])[-HINDSIGHT_K:].sum())
            for day in held_day_list]))}
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
def print_fold(calendar) -> None:
    print("\nINNER DEVELOPMENT FOLD (section 4 - constant iteration lives "
          "here, the CONFIRM blocks are never touched)", flush=True)
    if calendar is None:
        print("  none: the whole competence population is the fit block",
              flush=True)
        return
    print(f"  fold={calendar['fold']} era={calendar['era_start']}-"
          f"{calendar['era_end']} wall={calendar['wall']} "
          f"era_days={len(calendar['era_days'])}", flush=True)
    print(f"  FIT   ({len(calendar['fit_days'])}): "
          f"{list(calendar['fit_days'])}", flush=True)
    print(f"  SCORE ({len(calendar['score_days'])}): "
          f"{list(calendar['score_days'])}", flush=True)


def _print_column(label, column) -> None:
    if column is None:
        print(f"    {label:22s} (no scored day)", flush=True)
        return
    theta = ("n/a" if column["theta"] is None
             else f"{float(column['theta']):.4f}")
    print(f"    {label:22s} theta={theta:>8s} "
          f"portfolio=${column['portfolio_usd_day']:8.0f}/day "
          f"picks={column['picks_day']:.1f}/day "
          f"worst=${column['worst_day_usd']:8.0f} "
          + " ".join(f"{asset}=${value:.0f}" for asset, value
                     in sorted(column["per_asset_usd_day"].items())),
          flush=True)
    share = column.get("per_asset_pick_share", {})
    if share:
        print(f"    {'':22s} budget share: "
              + " ".join(f"{asset}={100 * value:.0f}%" for asset, value
                         in sorted(share.items())), flush=True)


def print_acceptance(acceptance) -> None:
    print("\nACCEPTANCE: ARRIVAL-ORDER GOAL-GRADE DOLLARS (sections 1/4/9)",
          flush=True)
    if not acceptance["days"]:
        print("  no held asset-day carried a compliant candidate slice",
              flush=True)
        return
    print(f"  scored_days={acceptance['days']} "
          f"train_days={acceptance['train_days']} "
          f"score={acceptance['score_key']} logit", flush=True)
    for kind, entry in acceptance["probes"].items():
        print(f"\n  ===== PROBE {kind.upper()} =====", flush=True)
        print("  per-asset HELD score quantiles (ruling 7 comparability "
              "evidence)", flush=True)
        for asset, quantiles in sorted(entry["score_quantiles"].items()):
            if quantiles:
                print(f"    {asset:>3} " + " ".join(
                    f"{name}={value:+.4f}" for name, value
                    in sorted(quantiles.items())), flush=True)
        for name, law_entry in entry["rules"].items():
            print(f"\n  RULE {name} (budget {law_entry['budget']}, "
                  f"per-asset cap {law_entry['per_asset_cap']})", flush=True)
            _print_column("memory (frozen)", law_entry["memory"])
            _print_column("memory (trailing q)",
                          law_entry.get("memory_trailing_quantile"))
            _print_column("memory (rank-norm)",
                          law_entry.get("memory_rank_normalized"))
            _print_column("shuffled null", law_entry["shuffled"])
            _print_column("occluded (ref)", law_entry["occluded"])
            oracle = law_entry["oracle"]
            print(f"    {'ORACLE':22s} {'':>14s} "
                  f"portfolio=${oracle['portfolio_usd_day']:8.0f}/day "
                  + " ".join(f"{asset}=${value:.0f}" for asset, value
                             in sorted(oracle["per_asset_usd_day"].items())),
                  flush=True)
            if "paired_margin_usd_day" in law_entry:
                print(f"    PAIRED memory-minus-shuffled="
                      f"${law_entry['paired_margin_usd_day']:.0f}/day  "
                      f"positive_days={law_entry['paired_positive_days']}"
                      f"/{law_entry['paired_days']}  "
                      f"beats_shuffled={law_entry['beats_shuffled']}  "
                      f"goal>=$7k:{law_entry['meets_portfolio_goal']}  "
                      f"min>=$6k:{law_entry['meets_portfolio_minimum']}",
                      flush=True)
        print("\n  TAIL VISIBILITY (held goal-grade rows, AUROC of score vs "
              "above/below-median net)", flush=True)
        for asset in sorted(entry["tail_visibility"]):
            live = entry["tail_visibility"][asset]
            shuffled = entry["tail_visibility_shuffled"].get(asset)
            print(f"    {asset:>3} memory="
                  + ("  n/a" if live is None else f"{live:.4f}")
                  + "  shuffled="
                  + ("  n/a" if shuffled is None else f"{shuffled:.4f}"),
                  flush=True)
        print("  HINDSIGHT TOP-3 (reference only - a lookahead coordinate "
              "system): " + " ".join(
                  f"{name}=${value:.0f}" for name, value
                  in sorted(entry["hindsight_reference"].items())), flush=True)
    print(f"\n  HINDSIGHT ORACLE (reference): "
          f"${acceptance['hindsight_reference']['oracle']:.0f}/day", flush=True)
    print("\n  DUAL-PROBE ACCEPTANCE (section 4: either probe passes, the "
          "shuffled null must fail both)", flush=True)
    for name, verdict in acceptance["dual"].items():
        print(f"    {name}: accepted={verdict['accepted']} "
              f"(either={verdict['accepted_either']} "
              f"null_fails_both={verdict['null_fails_both']}) "
              f"per_probe={verdict['per_probe_beats_shuffled']}", flush=True)


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
    parser.add_argument("--fold", type=int, default=0, choices=(0, 1, 2, 3),
                        help="inner development fold (0 = whole fit block)")
    parser.add_argument("--episode-cluster-collapse", action="store_true",
                        help="section 2 [A/B]: collapse episodes to their best "
                             "candidate in the listwise term")
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
    if args.episode_cluster_collapse:
        resources.EPISODE_CLUSTER_COLLAPSE = True
        applied["EPISODE_CLUSTER_COLLAPSE"] = True
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

    calendar = None
    encode_kwargs = {}
    if args.fold:
        calendar = fold_calendar(
            {int(batch.day) for batch in provider.batches}, args.fold)
        encode_kwargs["fit_days"] = frozenset(calendar["fit_days"])
    print_fold(calendar)

    encode_started = time.monotonic()
    rows, metrics, memories, _decoder, held_days, receipt = provider._encode(
        model, args.arm, **encode_kwargs)
    if calendar is not None:
        # The stage's own trailing held window lives INSIDE the fit block;
        # the fold's scored days are what the acceptance metric reads.
        inside = set(calendar["fit_days"])
        if not set(int(day) for day in held_days) <= inside:
            raise RuntimeError(
                "the stage validation window escaped the fold fit block")
        held_days = frozenset(calendar["score_days"])
    print(f"\nbase_stage {time.monotonic() - encode_started:.0f}s "
          f"(NONSEMANTIC wall clock)", flush=True)

    print_scope(receipt)
    print_identity(receipt)
    print_epoch_traces(receipt)
    print_gradient_shares(receipt)
    print(f"\nOPTIMIZER GROUPS (R8) {dict(receipt['optimizer_param_groups'])}",
          flush=True)

    from engine.entry_v2.neural_sufficiency_resources import (
        MEMORY_VALUE_SHUFFLE_SEED)
    probes = {"mlp": provider._memory_value_probes[args.arm],
              "linear": provider._memory_value_linear_probes[args.arm]}
    acceptance = arrival_acceptance(
        rows, memories, probes, device=provider.device,
        data_root=args.data_root, held_days=held_days,
        batches=provider.batches, shuffle_seed=MEMORY_VALUE_SHUFFLE_SEED,
        score_key=args.score_key,
        train_days=(None if calendar is None else calendar["fit_days"]))
    print_acceptance(acceptance)
    print(f"\nGATE-5 SANITY FLOOR joint_auroc={float(metrics[0]):.4f} "
          f"ap={float(metrics[1]):.4f} logloss={float(metrics[2]):.4f}",
          flush=True)

    if args.json_out:
        Path(args.json_out).expanduser().resolve().parent.mkdir(
            parents=True, exist_ok=True)
        payload = {
            "arm": args.arm, "applied_constants": applied,
            "fold": calendar,
            "acceptance": acceptance,
            "memory_value_linear_trace": list(
                receipt["memory_value_linear_trace"]),
            "memory_value_linear_margin": list(
                receipt["memory_value_linear_margin"]),
            "fit_block_days": (list(receipt["fit_block_days"])
                               if not isinstance(receipt["fit_block_days"], str)
                               else receipt["fit_block_days"]),
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
