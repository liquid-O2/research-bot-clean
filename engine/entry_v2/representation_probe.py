"""Held-forward E3 representation probe (diagnostic only).

This module deliberately depends on the immutable fold-store boundary.  It is
not imported by the campaign, training, model, or policy planes.
"""

from __future__ import annotations

import os
# Required by deterministic CUDA GEMM and intentionally set before torch import.
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import torch
from torch import Tensor, nn
import torch.nn.functional as F

from . import common as C
from .capacity_contract import ThresholdFeasibility, threshold_feasibility
from .contracts import (
    CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side,
)
from .fold_store import SCHEMA as FOLD_STORE_SCHEMA, load_fold
from .replay import ReplayOutcome, ScoredArrival, replay
from .teacher import TeacherPath, _chronological_action_supervision
from .train import FOLD_OOF_SCHEMA


SEED = 20260816
ASSETS = ("HG", "NKD", "SI")
FIT_DAYS = (20220701, 20220930)
CALIBRATION_DAYS = (20221001, 20221031)
TEST_DAYS = (20221101, 20221230)
WIDTH = 512
TOKENS_PER_INPUT = 4
PAIRWISE_MARGIN = 1.0
TRANSPORT_RATIO_EPSILON_USD = 1e-9
EXPECTED_AGGREGATE_SHA256 = (
    "10e6db318eb7493b8a96618d1ca7ea2123e9f3ec876e43636232e54360b9eb0f"
)
ADAPTER_SEEDS = {"embedding": SEED + 11, "static": SEED + 23,
                 "late_fusion": SEED + 37}
HEAD_SEED = SEED + 101
DEFAULT_FOLD = Path(
    "/workspace/artifacts/cache/port/entry_v2_runs/pre_h2_v4/folds/E3/primary"
)


@dataclass(frozen=True)
class ProbeRows:
    candidate_ids: tuple[str, ...]
    assets: tuple[str, ...]
    days: np.ndarray
    timestamps: np.ndarray
    embeddings: np.ndarray
    static_features: np.ndarray
    action: np.ndarray
    action_mask: np.ndarray
    expected_value: np.ndarray
    top3: np.ndarray
    wall: np.ndarray
    mae: np.ndarray

    def take(self, indices: np.ndarray) -> "ProbeRows":
        ids = tuple(self.candidate_ids[int(i)] for i in indices)
        assets = tuple(self.assets[int(i)] for i in indices)
        return ProbeRows(ids, assets, *(np.asarray(value)[indices] for value in (
            self.days, self.timestamps, self.embeddings, self.static_features,
            self.action, self.action_mask, self.expected_value, self.top3,
            self.wall, self.mae,
        )))


def reconstruct_action_supervision(
    arrivals: Sequence[ScoredArrival], truth_scores: Sequence[EntryScore]
) -> tuple[np.ndarray, np.ndarray]:
    if len(arrivals) != len(truth_scores):
        raise C.EntryV2Refusal("truth arrival/score length mismatch")
    paths = []
    for arrival, score in zip(arrivals, truth_scores):
        example = arrival.example
        if score.candidate_id != example.candidate_id:
            raise C.EntryV2Refusal("truth candidate order mismatch")
        exit_ts, _pnl, _reason = arrival.outcome.resolve(example.decision_ts_ns)
        paths.append(TeacherPath(
            example.candidate_id, example.asset, example.trading_day,
            example.decision_ts_ns, exit_ts, score.expected_pnl_usd,
            0.0, score.mae_p90_usd, score.wall_probability == 1.0, 0.0,
        ))
    selected, supervised = _chronological_action_supervision(tuple(paths))
    truth_selected = frozenset(
        score.candidate_id for score in truth_scores
        if score.take_probability == 1.0
    )
    if any(score.take_probability not in (0.0, 1.0) for score in truth_scores):
        raise C.EntryV2Refusal("PROPHET take_target is not binary")
    if selected != truth_selected:
        raise C.EntryV2Refusal("reconstructed action IDs differ from truth take_target IDs")
    ids = tuple(row.example.candidate_id for row in arrivals)
    return (np.asarray([candidate_id in selected for candidate_id in ids], bool),
            np.asarray([candidate_id in supervised for candidate_id in ids], bool))


def _sha256_ids(values: Iterable[str]) -> str:
    return hashlib.sha256(C.canonical_bytes(tuple(sorted(values)))).hexdigest()


def _sha256_array(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode())
    digest.update(C.canonical_bytes(array.shape))
    digest.update(array.tobytes())
    return digest.hexdigest()


def load_e3_rows(path: str | Path = DEFAULT_FOLD) -> tuple[Any, ProbeRows]:
    fold = load_fold(path)
    if (fold.fold != "E3" or fold.control_name != "PROPHET"
            or fold.receipt.get("schema") != FOLD_OOF_SCHEMA):
        raise C.EntryV2Refusal("probe requires E3/PROPHET/fold-oof-v4")
    receipt = json.loads((Path(path) / "receipt.json").read_text())
    if (receipt.get("schema") != FOLD_STORE_SCHEMA
            or receipt.get("fold") != "E3"
            or receipt.get("control_name") != "PROPHET"
            or receipt.get("aggregate_sha256") != EXPECTED_AGGREGATE_SHA256):
        raise C.EntryV2Refusal("probe requires fold-store-v3")
    days = np.asarray(fold.days, dtype=np.int64)
    session_days = np.asarray([session.trading_day for session in fold.expected_sessions])
    if np.any(days > TEST_DAYS[1]) or np.any(session_days > TEST_DAYS[1]):
        raise C.EntryV2Refusal("held-forward probe refuses H2 dates")
    action, action_mask = reconstruct_action_supervision(
        fold.truth_arrivals, fold.truth_scores
    )
    rows = ProbeRows(
        tuple(fold.candidate_ids), tuple(fold.assets), days,
        np.asarray([row.example.decision_ts_ns for row in fold.truth_arrivals]),
        np.asarray(fold.embeddings, dtype=np.float32),
        np.asarray(fold.static_features, dtype=np.float32), action, action_mask,
        np.asarray([s.expected_pnl_usd for s in fold.truth_scores], np.float32),
        np.asarray([s.top3_probability for s in fold.truth_scores], np.float32),
        np.asarray([s.wall_probability for s in fold.truth_scores], np.float32),
        np.asarray([s.mae_p90_usd for s in fold.truth_scores], np.float32),
    )
    return fold, rows


def split_rows(rows: ProbeRows, *, min_supervised_rows: int = 30
               ) -> Mapping[str, np.ndarray]:
    bounds = {"fit": FIT_DAYS, "calibration": CALIBRATION_DAYS, "test": TEST_DAYS}
    result: dict[str, np.ndarray] = {}
    for name, (lo, hi) in bounds.items():
        idx = np.flatnonzero((rows.days >= lo) & (rows.days <= hi))
        if not len(idx):
            raise C.EntryV2Refusal(f"{name} split is empty")
        supervised = idx[rows.action_mask[idx]]
        for asset in ASSETS:
            aset = supervised[np.asarray([rows.assets[i] == asset for i in supervised])]
            if len(aset) < min_supervised_rows or len(np.unique(rows.action[aset])) != 2:
                raise C.EntryV2Refusal(
                    f"{name}/{asset} lacks sufficient supervised rows/both classes"
                )
        result[name] = idx
    if any(set(result[a]) & set(result[b]) for a, b in (
        ("fit", "calibration"), ("fit", "test"), ("calibration", "test")
    )):
        raise C.EntryV2Refusal("probe split leakage")
    covered = np.concatenate(tuple(result.values()))
    if len(covered) != len(rows.days) or len(np.unique(covered)) != len(rows.days):
        raise C.EntryV2Refusal("candidate outside exact fit/calibration/test bounds")
    return result


@dataclass(frozen=True)
class FrozenNormalizer:
    mean: np.ndarray
    scale: np.ndarray
    constant: np.ndarray

    @classmethod
    def fit(cls, fit_values: np.ndarray) -> "FrozenNormalizer":
        values = np.asarray(fit_values, dtype=np.float64)
        if values.ndim != 2 or not len(values) or not np.all(np.isfinite(values)):
            raise C.EntryV2Refusal("normalizer requires a finite fit-only matrix")
        mean = values.mean(axis=0, dtype=np.float64)
        scale = values.std(axis=0, dtype=np.float64)
        constant = scale == 0.0
        scale[constant] = 1.0
        return cls(mean, scale, constant)

    def transform(self, values: np.ndarray) -> np.ndarray:
        transformed = ((np.asarray(values, dtype=np.float64) - self.mean) / self.scale)
        transformed[:, self.constant] = 0.0
        if not np.all(np.isfinite(transformed)):
            raise C.EntryV2Refusal("normalization produced non-finite values")
        return transformed.astype(np.float32)

    def receipt(self) -> Mapping[str, Any]:
        return {"schema": "entry-v2-probe-fit-normalizer-v1",
                "fit_only": True, "dtype": "float64", "columns": len(self.mean),
                "constant_columns": np.flatnonzero(self.constant).tolist(),
                "mean_sha256": _sha256_array(self.mean),
                "scale_sha256": _sha256_array(self.scale),
                "combined_sha256": hashlib.sha256(
                    self.mean.tobytes() + self.scale.tobytes()
                    + self.constant.tobytes()).hexdigest()}


def normalize_from_fit(rows: ProbeRows, fit_indices: np.ndarray
                       ) -> tuple[ProbeRows, Mapping[str, Any]]:
    embedding = FrozenNormalizer.fit(rows.embeddings[fit_indices])
    static = FrozenNormalizer.fit(rows.static_features[fit_indices])
    normalized = replace(rows, embeddings=embedding.transform(rows.embeddings),
                         static_features=static.transform(rows.static_features))
    return normalized, {"embedding": embedding.receipt(), "static": static.receipt()}


class InputAdapter(nn.Module):
    """Complete-vector adapter producing exactly four width-512 tokens."""
    def __init__(self, input_dim: int):
        super().__init__()
        self.projection = nn.Linear(input_dim, TOKENS_PER_INPUT * WIDTH)
        self.norm = nn.LayerNorm(WIDTH)

    def forward(self, value: Tensor) -> Tensor:
        return F.gelu(self.norm(self.projection(value).reshape(-1, TOKENS_PER_INPUT, WIDTH)))


class CrossAttentionBlock(nn.Module):
    def __init__(self):
        super().__init__()
        self.query_norm = nn.LayerNorm(WIDTH)
        self.memory_norm = nn.LayerNorm(WIDTH)
        self.attention = nn.MultiheadAttention(
            WIDTH, 8, dropout=0.0, batch_first=True
        )
        self.ffn_norm = nn.LayerNorm(WIDTH)
        self.ffn = nn.Sequential(
            nn.Linear(WIDTH, 2048), nn.GELU(), nn.Linear(2048, WIDTH)
        )

    def forward(self, query: Tensor, memory: Tensor) -> Tensor:
        norm_query = self.query_norm(query)
        attended, _ = self.attention(
            norm_query, self.memory_norm(memory), self.memory_norm(memory),
            need_weights=False,
        )
        query = query + attended
        return query + self.ffn(self.ffn_norm(query))


class SharedProbeHead(nn.Module):
    """The sole downstream head implementation used by every representation."""
    def __init__(self):
        super().__init__()
        self.candidate_query = nn.Parameter(torch.zeros(1, 1, WIDTH))
        self.asset_embedding = nn.Embedding(len(ASSETS), WIDTH)
        self.blocks = nn.ModuleList([CrossAttentionBlock(), CrossAttentionBlock()])
        self.action = nn.Linear(WIDTH, 1)
        self.expected_value = nn.Linear(WIDTH, 1)
        self.top3 = nn.Linear(WIDTH, 1)
        self.wall = nn.Linear(WIDTH, 1)
        self.mae = nn.Linear(WIDTH, 1)

    def forward(self, memory: Tensor, asset: Tensor) -> Mapping[str, Tensor]:
        query = self.candidate_query.expand(memory.shape[0], -1, -1)
        query = query + self.asset_embedding(asset).unsqueeze(1)
        for block in self.blocks:
            query = block(query, memory)
        hidden = query[:, 0]
        return {name: getattr(self, name)(hidden).squeeze(-1) for name in (
            "action", "expected_value", "top3", "wall", "mae"
        )}


class RepresentationModel(nn.Module):
    def __init__(self, representation: str, embedding_dim: int, static_dim: int):
        super().__init__()
        if representation not in {"embedding", "static", "late_fusion"}:
            raise ValueError("unknown representation")
        self.representation = representation
        torch.manual_seed(ADAPTER_SEEDS[representation])
        self.embedding_adapter = (InputAdapter(embedding_dim)
                                  if representation != "static" else None)
        self.static_adapter = (InputAdapter(static_dim)
                               if representation != "embedding" else None)
        # Adapter construction consumes a representation-specific RNG stream;
        # reset before the shared head so its initial bytes are invariant.
        torch.manual_seed(HEAD_SEED)
        self.head = SharedProbeHead()
        self.initial_head_sha256 = module_sha256(self.head)

    def forward(self, embedding: Tensor, static: Tensor, asset: Tensor
                ) -> Mapping[str, Tensor]:
        tokens = []
        if self.embedding_adapter is not None:
            tokens.append(self.embedding_adapter(embedding))
        if self.static_adapter is not None:
            tokens.append(self.static_adapter(static))
        return self.head(torch.cat(tokens, dim=1), asset)

    def architecture_receipt(self) -> Mapping[str, Any]:
        downstream = tuple((name, type(module).__name__) for name, module in
                           self.head.named_modules())
        return {"representation": self.representation,
                "memory_tokens": 8 if self.representation == "late_fusion" else 4,
                "width": WIDTH, "heads": 8, "ffn": 2048, "blocks": 2,
                "dropout": 0.0,
                "downstream_sha256": hashlib.sha256(
                    json.dumps(downstream, separators=(",", ":")).encode()
                ).hexdigest()}


def module_sha256(module: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(module.state_dict().items()):
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def configure_determinism() -> Mapping[str, Any]:
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)
    return {"seed": SEED, "deterministic_algorithms": True,
            "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
            "flash_sdp": False, "memory_efficient_sdp": False,
            "math_sdp": True}


def _exact_pos_weight_array(target: np.ndarray) -> float:
    raw = np.asarray(target)
    if not np.all(np.isin(raw, (0, 1))):
        raise C.EntryV2Refusal("exact class weight target is not binary")
    values = raw.astype(bool)
    positives = int(values.sum())
    negatives = len(values) - positives
    if positives <= 0 or negatives <= 0:
        raise C.EntryV2Refusal("exact class weight requires both classes")
    return negatives / positives


@dataclass(frozen=True)
class LossWeights:
    action: float
    top3: float
    wall: float

    @classmethod
    def from_fit(cls, rows: ProbeRows) -> "LossWeights":
        return cls(_exact_pos_weight_array(rows.action[rows.action_mask]),
                   _exact_pos_weight_array(rows.top3),
                   _exact_pos_weight_array(rows.wall))

    def as_dict(self) -> Mapping[str, float]:
        return {"action": self.action, "top3": self.top3, "wall": self.wall}


def probe_loss(outputs: Mapping[str, Tensor], targets: Mapping[str, Tensor],
               action_mask: Tensor, weights: LossWeights,
               pair_indices: Tensor | None = None) -> Tensor:
    if bool(action_mask.any()):
        action_logits = outputs["action"][action_mask]
        action_target = targets["action"][action_mask]
        loss = F.binary_cross_entropy_with_logits(
            action_logits, action_target,
            pos_weight=action_logits.new_tensor(weights.action)
        )
    else:
        loss = outputs["action"].sum() * 0.0
    loss = loss + F.smooth_l1_loss(
        outputs["expected_value"], targets["expected_value"] / 1000.0
    )
    for name in ("top3", "wall"):
        target = targets[name]
        loss = loss + F.binary_cross_entropy_with_logits(
            outputs[name], target,
            pos_weight=outputs[name].new_tensor(getattr(weights, name))
        )
    error = targets["mae"] / 900.0 - outputs["mae"]
    loss = loss + torch.maximum(0.90 * error, -0.10 * error).mean()
    if pair_indices is not None and pair_indices.numel():
        positive = outputs["action"][pair_indices[:, 0]]
        negative = outputs["action"][pair_indices[:, 1]]
        loss = loss + F.relu(PAIRWISE_MARGIN - positive + negative).mean()
    return loss


def _asset_tensor(assets: Sequence[str], device: torch.device) -> Tensor:
    lookup = {asset: index for index, asset in enumerate(ASSETS)}
    return torch.tensor([lookup[value] for value in assets], device=device)


def _tensors(rows: ProbeRows, device: torch.device) -> tuple[Tensor, Tensor, Tensor,
                                                               Mapping[str, Tensor], Tensor]:
    targets = {name: torch.as_tensor(getattr(rows, name), dtype=torch.float32,
                                     device=device) for name in (
        "action", "expected_value", "top3", "wall", "mae"
    )}
    return (torch.as_tensor(rows.embeddings, device=device),
            torch.as_tensor(rows.static_features, device=device),
            _asset_tensor(rows.assets, device), targets,
            torch.as_tensor(rows.action_mask, device=device))


def chronological_order(rows: ProbeRows) -> np.ndarray:
    return np.asarray(sorted(range(len(rows.candidate_ids)), key=lambda i: (
        int(rows.timestamps[i]), rows.candidate_ids[i]
    )), dtype=np.int64)


def _hard_pairs(rows: ProbeRows, logits: np.ndarray) -> np.ndarray:
    pairs = []
    groups: dict[tuple[str, int], list[int]] = {}
    for i, (asset, day) in enumerate(zip(rows.assets, rows.days)):
        if rows.action_mask[i]:
            groups.setdefault((asset, int(day)), []).append(i)
    for indices in groups.values():
        negatives = [i for i in indices if not rows.action[i]]
        if not negatives:
            continue
        hard = min(negatives, key=lambda i: (-float(logits[i]), rows.candidate_ids[i]))
        pairs.extend((i, hard) for i in indices if rows.action[i])
    return np.asarray(pairs, dtype=np.int64).reshape(-1, 2)


def train_models(rows: ProbeRows, representation: str, *, batch_size: int = 512,
                 device: str | None = None) -> Mapping[str, RepresentationModel]:
    """Two standard epochs, then one additional deterministic hard-tail epoch."""
    configure_determinism()
    selected_device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    if selected_device.type == "cuda":
        torch.cuda.manual_seed_all(SEED)
    model = RepresentationModel(
        representation, rows.embeddings.shape[1], rows.static_features.shape[1]
    ).to(selected_device)
    initial_state_hash = state_sha256(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-2)
    order = chronological_order(rows)
    weights = LossWeights.from_fit(rows)

    def epoch(pair_map: Mapping[int, list[tuple[int, int]]] | None = None) -> None:
        model.train()
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            batch = rows.take(idx)
            embedding, static, asset, targets, mask = _tensors(batch, selected_device)
            global_pairs = ([] if pair_map is None else
                            [pair for global_i in idx
                             for pair in pair_map.get(int(global_i), ())])
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=selected_device.type,
                                dtype=torch.bfloat16,
                                enabled=selected_device.type == "cuda"):
                loss = probe_loss(model(embedding, static, asset), targets, mask,
                                  weights)
                if global_pairs:
                    pair_index = np.asarray(global_pairs, dtype=np.int64).reshape(-1)
                    pair_rows = rows.take(pair_index)
                    pe, ps, pa, _pt, _pm = _tensors(pair_rows, selected_device)
                    pair_logits = model(pe, ps, pa)["action"].reshape(-1, 2)
                    loss = loss + F.relu(
                        PAIRWISE_MARGIN - pair_logits[:, 0] + pair_logits[:, 1]
                    ).mean()
            loss.backward()
            optimizer.step()

    epoch()
    training_history = [{"epoch": 1, "objective": "standard",
                         **full_fit_loss_components(
                             model, rows, selected_device, weights, None, batch_size)}]
    epoch()
    training_history.append({"epoch": 2, "objective": "standard",
                             **full_fit_loss_components(
                                 model, rows, selected_device, weights, None, batch_size)})
    standard = RepresentationModel(
        representation, rows.embeddings.shape[1], rows.static_features.shape[1]
    ).to(selected_device)
    standard.load_state_dict(model.state_dict())
    standard.initial_state_sha256 = initial_state_hash
    checkpoint_hash = state_sha256(standard)
    standard.standard_checkpoint_sha256 = checkpoint_hash
    standard.tail_start_sha256 = checkpoint_hash
    standard.training_history = tuple(training_history)
    logits = predict_logits(model, rows, selected_device, batch_size)["action"]
    pairs = _hard_pairs(rows, logits)
    pair_map: dict[int, list[tuple[int, int]]] = {}
    for positive, negative in pairs:
        pair_map.setdefault(int(positive), []).append((int(positive), int(negative)))
    model.standard_checkpoint_sha256 = checkpoint_hash
    model.initial_state_sha256 = initial_state_hash
    model.tail_start_sha256 = state_sha256(model)
    if model.tail_start_sha256 != checkpoint_hash:
        raise C.EntryV2Refusal("tail-aware model did not start exact standard checkpoint")
    epoch(pair_map)
    model.training_history = tuple((*training_history, {
        "epoch": 3, "objective": "hard_tail", "hard_pairs": len(pairs),
        **full_fit_loss_components(
            model, rows, selected_device, weights, pairs, batch_size)}))
    return {"standard": standard, "tail_aware": model}


@torch.no_grad()
def predict_logits(model: RepresentationModel, rows: ProbeRows,
                   device: torch.device | str, batch_size: int = 1024
                   ) -> Mapping[str, np.ndarray]:
    model.eval()
    selected_device = torch.device(device)
    collected = {name: [] for name in ("action", "expected_value", "top3", "wall", "mae")}
    for start in range(0, len(rows.candidate_ids), batch_size):
        idx = np.arange(start, min(len(rows.candidate_ids), start + batch_size))
        embedding, static, asset, _targets, _mask = _tensors(rows.take(idx), selected_device)
        output = model(embedding, static, asset)
        for name in collected:
            collected[name].append(output[name].float().cpu().numpy())
    return {name: np.concatenate(values) for name, values in collected.items()}


def _weighted_bce(logits: np.ndarray, target: np.ndarray, weight: float) -> float:
    x = np.asarray(logits, dtype=np.float64)
    y = np.asarray(target, dtype=np.float64)
    log_term = np.log1p(np.exp(-np.abs(x)))
    losses = ((1.0 - y) * (np.maximum(x, 0.0) + log_term)
              + y * weight * (np.maximum(-x, 0.0) + log_term))
    return float(losses.mean()) if len(losses) else 0.0


def full_fit_loss_components(model: RepresentationModel, rows: ProbeRows,
                             device: torch.device | str, weights: LossWeights,
                             pairs: np.ndarray | None, batch_size: int
                             ) -> Mapping[str, float]:
    """Evaluate the exact full-fit objective after an epoch, never a minibatch proxy."""
    output = predict_logits(model, rows, device, batch_size)
    supervised = rows.action_mask
    expected_error = (output["expected_value"].astype(np.float64)
                      - rows.expected_value.astype(np.float64) / 1000.0)
    expected_abs = np.abs(expected_error)
    expected_loss = float(np.mean(np.where(
        expected_abs < 1.0, 0.5 * expected_error ** 2, expected_abs - 0.5
    )))
    mae_error = (rows.mae.astype(np.float64) / 900.0
                 - output["mae"].astype(np.float64))
    components = {
        "action": _weighted_bce(output["action"][supervised],
                                rows.action[supervised], weights.action),
        "expected_value": expected_loss,
        "top3": _weighted_bce(output["top3"], rows.top3, weights.top3),
        "wall": _weighted_bce(output["wall"], rows.wall, weights.wall),
        "mae": float(np.maximum(0.90 * mae_error, -0.10 * mae_error).mean()),
        "pairwise": 0.0,
    }
    if pairs is not None and len(pairs):
        margin = (PAIRWISE_MARGIN - output["action"][pairs[:, 0]]
                  + output["action"][pairs[:, 1]])
        components["pairwise"] = float(np.maximum(margin, 0.0).mean())
    return {"full_fit_total": float(sum(components.values())),
            "full_fit_components": components}


@dataclass(frozen=True)
class MonotonePlatt:
    slope: float
    intercept: float

    @classmethod
    def fit(cls, logits: np.ndarray, targets: np.ndarray) -> "MonotonePlatt":
        x = torch.as_tensor(logits, dtype=torch.float64)
        y = torch.as_tensor(targets, dtype=torch.float64)
        if len(torch.unique(y)) != 2:
            raise C.EntryV2Refusal("Platt fit requires both classes")
        raw_slope = torch.tensor(0.0, dtype=torch.float64, requires_grad=True)
        intercept = torch.tensor(float(torch.logit(y.mean())), dtype=torch.float64,
                                 requires_grad=True)
        optimizer = torch.optim.LBFGS([raw_slope, intercept], max_iter=100,
                                      tolerance_grad=1e-12, line_search_fn="strong_wolfe")
        def closure() -> Tensor:
            optimizer.zero_grad()
            loss = F.binary_cross_entropy_with_logits(
                F.softplus(raw_slope) * x + intercept, y
            )
            loss.backward()
            return loss
        optimizer.step(closure)
        return cls(float(F.softplus(raw_slope).detach()), float(intercept.detach()))

    def predict(self, logits: np.ndarray) -> np.ndarray:
        z = np.clip(self.slope * np.asarray(logits) + self.intercept, -50, 50)
        return 1.0 / (1.0 + np.exp(-z))


def binary_metrics(target: np.ndarray, score: np.ndarray) -> Mapping[str, float | int]:
    target = np.asarray(target, bool)
    score = np.asarray(score, float)
    positives, negatives = int(target.sum()), int((~target).sum())
    if not positives or not negatives:
        raise C.EntryV2Refusal("metrics require both classes")
    order = np.argsort(score, kind="stable")
    ranks = np.empty(len(score), float)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and score[order[j]] == score[order[i]]:
            j += 1
        ranks[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    auroc = (ranks[target].sum() - positives * (positives + 1) / 2) / (positives * negatives)
    descending = np.argsort(-score, kind="stable")
    cumulative = np.cumsum(target[descending])
    ap = float(np.sum((cumulative / np.arange(1, len(score) + 1))[target[descending]]) / positives)
    # V18: AUROC / AP / Brier are CLASSIFICATION metrics.  They are never a
    # promotion basis (the promotion basis is exact chronological asset-day
    # dollars, candidate-oracle capture and per-asset drawdown), so each
    # published entry carries its own diagnostic-only marker the way
    # audit.py's promotion receipt does.
    return {"auroc": float(auroc), "average_precision": ap,
            "brier": float(np.mean((score - target) ** 2)),
            "unique_scores": int(len(np.unique(score))),
            "diagnostic_only": True,
            "diagnostic_only_metrics": ["auroc", "average_precision", "brier"],
            "promotion_eligible_metrics": [
                "per_asset_exact_arrival_replay_dollars",
                "per_asset_candidate_oracle_capture",
                "per_asset_expectancy_and_max_drawdown"]}


def _topk_view(rows: ProbeRows, scores: np.ndarray, eligible: np.ndarray
               ) -> Mapping[str, Any]:
    receipt: dict[str, Any] = {"per_asset_day": {}, "global": {}}
    for k in (1, 3):
        selected = []
        groups: dict[tuple[str, int], list[int]] = {}
        for i, key in enumerate(zip(rows.assets, rows.days)):
            if eligible[i]:
                groups.setdefault((key[0], int(key[1])), []).append(i)
        for indices in groups.values():
            selected.extend(sorted(indices, key=lambda i: (
                -float(scores[i]), rows.candidate_ids[i]
            ))[:k])
        truth = eligible & rows.action
        hits = int(rows.action[selected].sum())
        receipt["per_asset_day"][str(k)] = {
            "precision": hits / len(selected) if selected else 0.0,
            "recall": hits / int(truth.sum()) if truth.any() else 0.0,
        }
    eligible_indices = np.flatnonzero(eligible)
    ranked = sorted(eligible_indices, key=lambda i: (
        -float(scores[i]), rows.candidate_ids[i]
    ))
    positives = int(rows.action[eligible_indices].sum())
    for k in (10, 25, 50, 100, 250):
        chosen = ranked[:k]
        hits = int(rows.action[chosen].sum())
        receipt["global"][str(k)] = {"precision": hits / len(chosen) if chosen else 0.0,
                                        "recall": hits / positives if positives else 0.0}
    return receipt


def topk_metrics(rows: ProbeRows, scores: np.ndarray) -> Mapping[str, Any]:
    return {"primary_action_supervised": _topk_view(rows, scores, rows.action_mask),
            "deploy_all_candidates": _topk_view(
                rows, scores, np.ones(len(rows.candidate_ids), dtype=bool)
            )}


def _scored_rows(fold: Any, indices: np.ndarray, scores: np.ndarray,
                 thresholds: Mapping[str, float], model_hash: str
                 ) -> tuple[ScoredArrival, ...]:
    result = []
    for local, global_i in enumerate(indices):
        source = fold.truth_arrivals[int(global_i)]
        probability = float(scores[local])
        score = replace(source.score, model_hash=model_hash,
                        priority_score=probability, take_probability=probability,
                        enter=probability >= thresholds[source.example.asset])
        result.append(ScoredArrival(source.example, score, source.outcome))
    return tuple(result)


def _sessions(fold: Any, lo: int, hi: int, asset: str | None = None
              ) -> tuple[SessionRef, ...]:
    return tuple(s for s in fold.expected_sessions
                 if lo <= s.trading_day <= hi and (asset is None or s.asset == asset))


@dataclass(frozen=True)
class ThresholdSweep:
    thresholds: np.ndarray
    action_pass: np.ndarray
    trades: np.ndarray
    total_pnl_usd: np.ndarray
    usd_per_trade: np.ndarray
    usd_per_asset_day: np.ndarray
    max_drawdown_usd: np.ndarray
    drawdown_p90_usd: np.ndarray
    eligible_days: tuple[int, ...]
    daily_trades: np.ndarray
    daily_admissions: np.ndarray
    daily_pnl_usd: np.ndarray
    days_with_trades: np.ndarray
    receipt_sha256: str = ""

    def __post_init__(self) -> None:
        vectors = ("thresholds", "action_pass", "trades", "total_pnl_usd",
                   "usd_per_trade", "usd_per_asset_day", "max_drawdown_usd",
                   "drawdown_p90_usd", "days_with_trades")
        width = len(np.asarray(self.thresholds))
        if (not width or len(set(self.eligible_days)) != len(self.eligible_days)
                or tuple(sorted(self.eligible_days)) != self.eligible_days
                or any(not isinstance(day, (int, np.integer))
                       for day in self.eligible_days)):
            raise C.EntryV2Refusal("threshold sweep chronology is invalid")
        for name in vectors:
            value = np.ascontiguousarray(getattr(self, name)).copy()
            if value.shape != (width,):
                raise C.EntryV2Refusal("threshold sweep vectors are misaligned")
            if (name not in {"action_pass", "trades", "days_with_trades"}
                    and not np.all(np.isfinite(value))):
                raise C.EntryV2Refusal("threshold sweep contains non-finite values")
            value.setflags(write=False); object.__setattr__(self, name, value)
        daily = np.ascontiguousarray(self.daily_trades, np.int64).copy()
        admissions = np.ascontiguousarray(self.daily_admissions, np.int64).copy()
        daily_pnl = np.ascontiguousarray(self.daily_pnl_usd, np.float64).copy()
        if (daily.shape != (width, len(self.eligible_days))
                or admissions.shape != daily.shape or daily_pnl.shape != daily.shape
                or np.any(daily < 0) or np.any(admissions < 0)
                or not np.all(np.isfinite(daily_pnl))
                or not np.array_equal(daily.sum(axis=1), self.trades)
                or not np.array_equal(admissions.sum(axis=1), self.action_pass)
                or np.any(admissions < daily)
                or not np.allclose(daily_pnl.sum(axis=1), self.total_pnl_usd,
                                   rtol=0.0, atol=1e-9)
                or not np.array_equal((daily > 0).sum(axis=1), self.days_with_trades)):
            raise C.EntryV2Refusal("threshold sweep daily trades do not reconcile")
        for name, value in (("daily_trades", daily),
                            ("daily_admissions", admissions),
                            ("daily_pnl_usd", daily_pnl)):
            value.setflags(write=False); object.__setattr__(self, name, value)
        core = {"schema": "entry-v2-threshold-sweep-v2",
                "eligible_days": self.eligible_days,
                **{name: _semantic_array_sha256(np.asarray(getattr(self, name)))
                   for name in vectors},
                "daily_trades": _semantic_array_sha256(daily),
                "daily_admissions": _semantic_array_sha256(admissions),
                "daily_pnl_usd": _semantic_array_sha256(daily_pnl)}
        expected = C.object_sha256(core)
        if self.receipt_sha256 and self.receipt_sha256 != expected:
            raise C.EntryV2Refusal("threshold sweep receipt differs from its arrays")
        object.__setattr__(self, "receipt_sha256", expected)


def _semantic_array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode()); digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


def threshold_candidates(probability: np.ndarray) -> np.ndarray:
    values = np.asarray(probability, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.all(np.isfinite(values)):
        raise C.EntryV2Refusal("invalid Platt threshold surface")
    levels = np.unique(values)
    sentinel = np.nextafter(levels[-1], np.inf)
    return np.concatenate((levels, np.asarray([sentinel])))


def fast_threshold_sweep(arrivals: Sequence[ScoredArrival], probability: np.ndarray,
                         expected_sessions: Sequence[SessionRef]) -> ThresholdSweep:
    """Exact one-asset replay for every distinct threshold in one state sweep."""
    rows = tuple(arrivals)
    scores = np.asarray(probability, dtype=np.float64)
    if len(rows) != len(scores) or not rows:
        raise C.EntryV2Refusal("threshold sweep rows/scores mismatch")
    assets = {row.example.asset for row in rows}
    session_assets = {session.asset for session in expected_sessions}
    if len(assets) != 1 or assets != session_assets:
        raise C.EntryV2Refusal("threshold sweep requires exactly one asset")
    expected_set = set(expected_sessions)
    if any(row.example.session not in expected_set for row in rows):
        raise C.EntryV2Refusal("candidate outside threshold sweep sessions")
    thresholds = threshold_candidates(scores)
    width = len(thresholds)
    days = sorted({session.trading_day for session in expected_sessions})
    if not days:
        raise C.EntryV2Refusal("threshold sweep denominator is empty")
    day_column = {day: i for i, day in enumerate(days)}
    daily_cumulative = np.zeros((width, len(days)), dtype=np.float64)
    daily_peak = np.zeros((width, len(days)), dtype=np.float64)
    daily_mdd = np.zeros((width, len(days)), dtype=np.float64)
    open_until = np.full(width, -1, dtype=np.int64)
    day_count = np.zeros((width, len(days)), dtype=np.int16)
    # Admissions are threshold-positive candidate decisions before replay
    # occupancy/caps; trades are the subset executed by canonical replay.
    daily_admissions = np.zeros((width, len(days)), dtype=np.int64)
    for column, day in enumerate(days):
        day_scores = np.sort(np.asarray([
            scores[i] for i, row in enumerate(rows)
            if row.example.trading_day == day
        ], np.float64))
        if len(day_scores):
            daily_admissions[:, column] = (
                len(day_scores)
                - np.searchsorted(day_scores, thresholds, side="left"))
    trades = np.zeros(width, dtype=np.int64)
    total = np.zeros(width, dtype=np.float64)
    cumulative = np.zeros(width, dtype=np.float64)
    peak = np.zeros(width, dtype=np.float64)
    mdd = np.zeros(width, dtype=np.float64)
    sorted_scores = np.sort(scores)
    action_pass = len(scores) - np.searchsorted(sorted_scores, thresholds, side="left")
    ordered = sorted(range(len(rows)), key=lambda i: (
        rows[i].example.decision_ts_ns, rows[i].example.candidate_id
    ))
    cursor = 0
    while cursor < len(ordered):
        timestamp = rows[ordered[cursor]].example.decision_ts_ns
        end = cursor + 1
        while end < len(ordered) and rows[ordered[end]].example.decision_ts_ns == timestamp:
            end += 1
        group = ordered[cursor:end]
        group_days = {rows[i].example.trading_day for i in group}
        if len(group_days) != 1:
            raise C.EntryV2Refusal("one timestamp crosses trading days")
        day = next(iter(group_days))
        if day not in day_column:
            raise C.EntryV2Refusal("candidate outside threshold denominator")
        column = day_column[day]
        winner_index = min(group, key=lambda i: (
            -scores[i], rows[i].example.candidate_id
        ))
        winner = rows[winner_index]
        take = ((thresholds <= scores[winner_index])
                & (open_until < timestamp)
                & (day_count[:, column] < C.MAX_ENTRIES_PER_ASSET_DAY))
        if np.any(take):
            exit_ts, pnl, _reason = winner.outcome.resolve(timestamp)
            open_until[take] = exit_ts
            day_count[take, column] += 1
            trades[take] += 1
            total[take] += pnl
            cumulative[take] += pnl
            peak[take] = np.maximum(peak[take], cumulative[take])
            mdd[take] = np.maximum(mdd[take], peak[take] - cumulative[take])
            daily_cumulative[take, column] += pnl
            daily_peak[take, column] = np.maximum(
                daily_peak[take, column], daily_cumulative[take, column]
            )
            daily_mdd[take, column] = np.maximum(
                daily_mdd[take, column],
                daily_peak[take, column] - daily_cumulative[take, column]
            )
        cursor = end
    p90_index = max(0, math.ceil(0.90 * len(days)) - 1)
    drawdown_p90 = np.sort(daily_mdd, axis=1)[:, p90_index]
    usd_per_trade = np.divide(total, trades, out=np.zeros_like(total), where=trades > 0)
    days_with_trades = np.sum(day_count > 0, axis=1, dtype=np.int64)
    return ThresholdSweep(
        thresholds, action_pass, trades, total, usd_per_trade,
        total / len(days), mdd, drawdown_p90, tuple(days), day_count,
        daily_admissions, daily_cumulative, days_with_trades)


def _canonical_threshold_eval(arrivals: Sequence[ScoredArrival], probability: np.ndarray,
                              threshold: float, sessions: Sequence[SessionRef]):
    scored = tuple(ScoredArrival(row.example, replace(
        row.score, model_hash="probe-sweep-parity", priority_score=float(probability[i]),
        take_probability=float(probability[i]), enter=float(probability[i]) >= threshold
    ), row.outcome) for i, row in enumerate(arrivals))
    return replay(scored, expected_sessions=sessions)


def assert_fast_sweep_parity(arrivals: Sequence[ScoredArrival], probability: np.ndarray,
                             sessions: Sequence[SessionRef], sweep: ThresholdSweep,
                             *, samples: int = 9) -> str:
    indices = np.unique(np.linspace(0, len(sweep.thresholds) - 1,
                                    min(samples, len(sweep.thresholds)), dtype=int))
    evidence = []
    for i in indices:
        result = _canonical_threshold_eval(
            arrivals, probability, float(sweep.thresholds[i]), sessions
        )
        observed = (result.trades, result.total_pnl_usd, result.usd_per_trade,
                    result.usd_per_asset_day, result.max_drawdown_usd,
                    result.drawdown_p90_usd,
                    sum(row.trades > 0 for row in result.asset_day_results))
        expected = (int(sweep.trades[i]), float(sweep.total_pnl_usd[i]),
                    float(sweep.usd_per_trade[i]), float(sweep.usd_per_asset_day[i]),
                    float(sweep.max_drawdown_usd[i]), float(sweep.drawdown_p90_usd[i]),
                    int(sweep.days_with_trades[i]))
        if not all(math.isclose(float(a), float(b), rel_tol=0.0, abs_tol=1e-9)
                   for a, b in zip(observed, expected)):
            raise C.EntryV2Refusal(f"fast threshold sweep differs from replay at {i}")
        daily = tuple(row.trades for row in result.asset_day_results)
        if daily != tuple(int(value) for value in sweep.daily_trades[i]):
            raise C.EntryV2Refusal(
                f"fast threshold daily trades differ from replay at {i}")
        daily_pnl = tuple(float(row.pnl_usd) for row in result.asset_day_results)
        daily_admissions = tuple(sum(
            row.example.trading_day == day
            and float(probability[index]) >= float(sweep.thresholds[i])
            for index, row in enumerate(arrivals)
        ) for day in sweep.eligible_days)
        if (daily_admissions != tuple(int(value) for value in
                                      sweep.daily_admissions[i])
                or any(not math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)
                       for a, b in zip(daily_pnl, sweep.daily_pnl_usd[i]))):
            raise C.EntryV2Refusal(
                f"fast threshold daily admission/PnL differs from replay at {i}")
        evidence.append((int(i), expected, daily, daily_admissions, daily_pnl,
                         sweep.receipt_sha256))
    return hashlib.sha256(C.canonical_bytes(evidence)).hexdigest()


def canonical_replay_adversary_receipt() -> Mapping[str, Any]:
    """Exercise replay edge laws inside the production rehearsal.

    The authoritative fit-only corpus need not contain every exact tie/cap
    combination.  This deterministic adversary therefore runs through the
    same production sweep and canonical replay functions on every invocation;
    it is evidence, not a unit-test assertion substituted for execution.
    """
    day = 20210802
    specifications = (
        ("tie-a", 10, 20, -200.0, .8, None),
        ("tie-b", 10, 11, 900.0, .8, None),
        ("equal-open", 20, 21, 1000.0, .9, None),
        ("after", 21, 22, 800.0, .7, None),
        ("wall", 23, 25, 1000.0, .6, 24),
        ("capped", 25, 26, 2000.0, .5, None),
    )
    prefix = RawPrefixRef("replay-adversary", 0, 0, 0, None, None, "0" * 64)
    rows = []
    probability = []
    for candidate_id, decision, close, pnl, score, wall in specifications:
        example = CausalEntryExample(
            candidate_id, "SI", day, f"SI-{day}", decision, Side.LONG,
            "ADVERSARY", 0, prefix, {}, None, "1" * 64,
        )
        entry_score = EntryScore(
            candidate_id, "SI", decision, "replay-adversary", score, score,
            pnl, pnl, 0.0, 0.0, float(wall is not None), False,
        )
        outcome = ReplayOutcome(
            candidate_id, close, pnl, close, pnl,
            wall_hit_ts_ns=wall, wall_pnl_usd=-900.0,
        )
        rows.append(ScoredArrival(example, entry_score, outcome))
        probability.append(score)
    rows = tuple(rows)
    probability_array = np.asarray(probability, np.float64)
    sessions = (
        SessionRef("SI", day, f"SI-{day}"),
        SessionRef("SI", 20210803, "SI-20210803-empty"),
    )
    sweep = fast_threshold_sweep(rows, probability_array, sessions)
    parity_sha256 = assert_fast_sweep_parity(
        rows, probability_array, sessions, sweep, samples=len(sweep.thresholds))
    index = int(np.flatnonzero(sweep.thresholds == .8)[0])
    at_tie = _canonical_threshold_eval(rows, probability_array, .8, sessions)
    tie_ids = tuple(trade.candidate_id for trade in at_tie.trade_results)
    if (tie_ids != ("tie-a",) or int(sweep.trades[index]) != 1
            or float(sweep.total_pnl_usd[index]) != -200.0
            or tuple(map(int, sweep.daily_trades[index])) != (1, 0)
            or tuple(map(int, sweep.daily_admissions[index])) != (3, 0)
            or at_tie.asset_days != 2):
        raise C.EntryV2Refusal("canonical equal-time replay adversary differs")
    at_all = _canonical_threshold_eval(rows, probability_array, .5, sessions)
    all_ids = tuple(trade.candidate_id for trade in at_all.trade_results)
    all_reasons = tuple(trade.exit_reason.value for trade in at_all.trade_results)
    if all_ids != ("tie-a", "after", "wall") or all_reasons[-1] != "WALL":
        raise C.EntryV2Refusal("canonical occupancy/cap/wall replay adversary differs")
    evidence = {
        "schema": "entry-v2-canonical-replay-adversary-v1",
        "parity_sha256": parity_sha256,
        "equal_timestamp_candidates": ["tie-a", "tie-b"],
        "equal_timestamp_winner": "tie-a",
        "equal_exit_blocked_candidate": "equal-open",
        "asset_cap_blocked_candidate": "capped",
        "wall_exit_candidate": "wall",
        "empty_denominator_day": 20210803,
        "all_threshold_trade_ids": list(all_ids),
        "threshold_sweep_sha256": sweep.receipt_sha256,
    }
    evidence["receipt_sha256"] = hashlib.sha256(
        C.canonical_bytes(evidence)).hexdigest()
    return evidence


@dataclass(frozen=True)
class DepthFunnelReceipt:
    threshold: float
    trades: int
    total_pnl_usd: float
    usd_per_trade: float
    usd_per_asset_day: float
    eligible_days: int
    days_with_trades: int
    executed_trade_precision: float
    max_drawdown_usd: float
    trade_candidate_ids: tuple[str, ...]
    feasibility_receipt_sha256: str
    feasible: bool
    diagnostic_only: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        core = {
            "schema": "entry-v2-depth-funnel-diagnostic-v1",
            "threshold": self.threshold, "trades": self.trades,
            "total_pnl_usd": self.total_pnl_usd,
            "usd_per_trade": self.usd_per_trade,
            "usd_per_asset_day": self.usd_per_asset_day,
            "eligible_days": self.eligible_days,
            "days_with_trades": self.days_with_trades,
            "executed_trade_precision": self.executed_trade_precision,
            "max_drawdown_usd": self.max_drawdown_usd,
            "feasibility_receipt_sha256": self.feasibility_receipt_sha256,
            "feasible": self.feasible, "diagnostic_only": self.diagnostic_only,
            "trade_candidate_ids": list(self.trade_candidate_ids),
        }
        if (not self.diagnostic_only or self.trades != len(self.trade_candidate_ids)
                or C.object_sha256(core) != self.receipt_sha256):
            raise C.EntryV2Refusal("depth funnel receipt is not self-consistent")

    def __bool__(self) -> bool:
        raise C.EntryV2Refusal("diagnostic depth receipt cannot enter selection")


def depth_funnel(
    arrivals: Sequence[ScoredArrival], probability: np.ndarray, threshold: float,
    expected_sessions: Sequence[SessionRef], *,
    positive_candidate_ids: Sequence[str],
) -> DepthFunnelReceipt:
    """Measure deployable depth through the canonical replay, never selection."""
    rows = tuple(arrivals); scores = np.asarray(probability, np.float64)
    positive = frozenset(map(str, positive_candidate_ids))
    row_ids = {row.example.candidate_id for row in rows}
    if (not rows or scores.shape != (len(rows),) or not np.all(np.isfinite(scores))
            or not math.isfinite(float(threshold)) or not positive <= row_ids):
        raise C.EntryV2Refusal("depth funnel inputs are invalid")
    result = _canonical_threshold_eval(rows, scores, float(threshold), expected_sessions)
    days_with_trades = sum(row.trades > 0 for row in result.asset_day_results)
    executed_precision = (
        sum(trade.candidate_id in positive for trade in result.trade_results)
        / result.trades if result.trades else 0.0)
    feasibility = threshold_feasibility(
        trades=result.trades, usd_per_trade=result.usd_per_trade,
        max_drawdown_usd=result.max_drawdown_usd,
        days_with_trades=days_with_trades, eligible_days=result.asset_days)
    core = {
        "schema": "entry-v2-depth-funnel-diagnostic-v1",
        "threshold": float(threshold), "trades": result.trades,
        "total_pnl_usd": result.total_pnl_usd,
        "usd_per_trade": result.usd_per_trade,
        "usd_per_asset_day": result.usd_per_asset_day,
        "eligible_days": result.asset_days,
        "days_with_trades": days_with_trades,
        "executed_trade_precision": executed_precision,
        "max_drawdown_usd": result.max_drawdown_usd,
        "feasibility_receipt_sha256": feasibility.receipt_sha256,
        "feasible": feasibility.feasible, "diagnostic_only": True,
        "trade_candidate_ids": [row.candidate_id for row in result.trade_results],
    }
    return DepthFunnelReceipt(
        float(threshold), result.trades, result.total_pnl_usd,
        result.usd_per_trade, result.usd_per_asset_day, result.asset_days,
        days_with_trades, executed_precision, result.max_drawdown_usd,
        tuple(row.candidate_id for row in result.trade_results),
        feasibility.receipt_sha256, feasibility.feasible, True,
        C.object_sha256(core))


@dataclass(frozen=True)
class TransportReceipt:
    frozen_depth_sha256: str
    held_optimum_depth_sha256: str
    twin_depth_sha256: str
    frozen_vs_held_optimum_ratio: float
    ratio_denominator_usd: float
    held_optimum_nonpositive: bool
    twin_false_feasibility: bool
    diagnostic_only: bool
    receipt_sha256: str

    def __post_init__(self) -> None:
        core = {
            "schema": "entry-v2-transport-diagnostic-v1",
            "frozen_depth_sha256": self.frozen_depth_sha256,
            "held_optimum_depth_sha256": self.held_optimum_depth_sha256,
            "twin_depth_sha256": self.twin_depth_sha256,
            "frozen_vs_held_optimum_ratio": self.frozen_vs_held_optimum_ratio,
            "ratio_denominator_usd": self.ratio_denominator_usd,
            "held_optimum_nonpositive": self.held_optimum_nonpositive,
            "twin_false_feasibility": self.twin_false_feasibility,
            "diagnostic_only": self.diagnostic_only,
        }
        if not self.diagnostic_only or C.object_sha256(core) != self.receipt_sha256:
            raise C.EntryV2Refusal("transport receipt is not self-consistent")

    def __bool__(self) -> bool:
        raise C.EntryV2Refusal("diagnostic transport receipt cannot enter selection")


def transport_receipt(
    frozen: DepthFunnelReceipt, held_optimum: DepthFunnelReceipt,
    twin: DepthFunnelReceipt,
) -> TransportReceipt:
    """Compare diagnostic transport without creating a selection input."""
    if (type(frozen) is not DepthFunnelReceipt
            or type(held_optimum) is not DepthFunnelReceipt
            or type(twin) is not DepthFunnelReceipt
            or not all(row.diagnostic_only for row in (frozen, held_optimum, twin))):
        raise C.EntryV2Refusal("transport diagnostics are invalid")
    nonpositive = held_optimum.usd_per_asset_day <= 0
    denominator = max(held_optimum.usd_per_asset_day,
                      TRANSPORT_RATIO_EPSILON_USD)
    ratio = frozen.usd_per_asset_day / denominator
    if not math.isfinite(ratio):
        raise C.EntryV2Refusal("transport ratio is non-finite")
    core = {
        "schema": "entry-v2-transport-diagnostic-v1",
        "frozen_depth_sha256": frozen.receipt_sha256,
        "held_optimum_depth_sha256": held_optimum.receipt_sha256,
        "twin_depth_sha256": twin.receipt_sha256,
        "frozen_vs_held_optimum_ratio": ratio,
        "ratio_denominator_usd": denominator,
        "held_optimum_nonpositive": nonpositive,
        "twin_false_feasibility": twin.feasible,
        "diagnostic_only": True,
    }
    return TransportReceipt(
        frozen.receipt_sha256, held_optimum.receipt_sha256, twin.receipt_sha256,
        ratio, denominator, nonpositive, twin.feasible, True,
        C.object_sha256(core))


def select_thresholds(fold: Any, indices: np.ndarray, calibrated: np.ndarray
                      ) -> tuple[Mapping[str, float], Mapping[str, Any]]:
    thresholds: dict[str, float] = {}
    funnels: dict[str, Any] = {}
    for asset in ASSETS:
        local = np.flatnonzero(np.asarray([fold.assets[int(i)] == asset for i in indices]))
        candidates = tuple(fold.truth_arrivals[int(i)] for i in indices[local])
        sessions = _sessions(fold, *CALIBRATION_DAYS, asset)
        sweep = fast_threshold_sweep(candidates, calibrated[local], sessions)
        parity_hash = assert_fast_sweep_parity(candidates, calibrated[local], sessions, sweep)
        feasibility = tuple(threshold_feasibility(
            trades=int(sweep.trades[i]),
            usd_per_trade=float(sweep.usd_per_trade[i]),
            max_drawdown_usd=float(sweep.max_drawdown_usd[i]),
            days_with_trades=int(sweep.days_with_trades[i]),
            eligible_days=len(sweep.eligible_days),
        ) for i in range(len(sweep.thresholds)))
        feasible = np.asarray([row.feasible for row in feasibility], bool)
        funnel = []
        for i, threshold in enumerate(sweep.thresholds):
            reasons = feasibility[i].reasons
            funnel.append({"threshold": float(threshold),
                "candidate_count": len(candidates),
                "action_pass": int(sweep.action_pass[i]), "trades": int(sweep.trades[i]),
                "days_with_trades": int(sweep.days_with_trades[i]),
                "eligible_days": len(sweep.eligible_days),
                "total_pnl_usd": float(sweep.total_pnl_usd[i]),
                "usd_per_trade": float(sweep.usd_per_trade[i]),
                "usd_per_asset_day": float(sweep.usd_per_asset_day[i]),
                "max_drawdown_usd": float(sweep.max_drawdown_usd[i]),
                "drawdown_p90_usd": float(sweep.drawdown_p90_usd[i]),
                "feasible": bool(feasible[i]),
                "feasibility_receipt_sha256": feasibility[i].receipt_sha256,
                "sweep_receipt_sha256": sweep.receipt_sha256,
                "reason": "FEASIBLE" if not reasons else "+".join(reasons)})
        feasible_indices = np.flatnonzero(feasible)
        if not len(feasible_indices):
            # V4: with zero feasible thresholds the sweep's no-entry sentinel
            # publishes trades:0 / $0 / MDD:0.  Those are the arithmetic of an
            # EMPTY book, not an economic result, and a consumer that read the
            # rows without reading ``status`` saw a clean zero-drawdown row.
            # The branch is typed and every consumer must inspect it.
            chosen = len(sweep.thresholds) - 1
            typed_reason = "NO_FEASIBLE_THRESHOLD"
            status = "NO_FEASIBLE_THRESHOLD"
        else:
            chosen = max(feasible_indices, key=lambda i: (
                float(sweep.usd_per_asset_day[i]), float(sweep.usd_per_trade[i]),
                -float(sweep.max_drawdown_usd[i]), -float(sweep.drawdown_p90_usd[i]),
                float(sweep.thresholds[i]), int(sweep.trades[i])))
            typed_reason = None
            status = "ELIGIBLE"
        thresholds[asset] = float(sweep.thresholds[chosen])
        funnels[asset] = {"selected_index": int(chosen), "reason": typed_reason,
                          "status": status,
                          "economics_publishable": status == "ELIGIBLE",
                          "no_entry_sentinel_threshold":
                              float(sweep.thresholds[-1]),
                          "selected_trades": int(sweep.trades[chosen]),
                          "feasible_thresholds": int(feasible.sum()),
                          "fast_replay_parity_sha256": parity_hash,
                          "candidates": funnel}
    return thresholds, funnels


def assert_threshold_funnels_publishable(funnels: Mapping[str, Any]) -> None:
    """Refuse to treat a NO_FEASIBLE_THRESHOLD funnel as an economic result.

    V4: consumers that publish per-asset dollars/MDD must call this first so a
    typed empty book can never be reported as a clean $0 / zero-drawdown row.
    """
    for asset in sorted(funnels):
        row = funnels[asset]
        if not isinstance(row, Mapping) or "status" not in row:
            raise C.EntryV2Refusal(
                f"{asset} threshold funnel lacks its typed status")
        if row["status"] != "ELIGIBLE":
            raise C.EntryV2Refusal(
                f"{asset} threshold funnel is typed {row['status']}; its "
                "trades/PnL/drawdown columns are an empty book, not economics")


def state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _evaluation_receipt(value: Any) -> Mapping[str, Any]:
    fields = ("asset_days", "trades", "total_pnl_usd", "usd_per_asset_day",
              "usd_per_trade", "zero_asset_days", "worst_asset_day_usd",
              "max_drawdown_usd", "drawdown_p90_usd", "drawdown_breach_rate")
    return {**{name: getattr(value, name) for name in fields},
            "by_asset": {row.asset: {
                "asset_days": row.asset_days, "trades": row.trades,
                "total_pnl_usd": row.total_pnl_usd,
                "usd_per_asset_day": row.usd_per_asset_day,
                "usd_per_trade": row.usd_per_trade,
                "zero_asset_days": row.zero_asset_days,
                "worst_asset_day_usd": row.worst_asset_day_usd,
                "max_drawdown_usd": row.max_drawdown_usd,
                "drawdown_p90_usd": row.drawdown_p90_usd,
                "drawdown_breach_rate": row.drawdown_breach_rate,
            } for row in value.by_asset}}


def _split_receipt(rows: ProbeRows, splits: Mapping[str, np.ndarray]
                   ) -> Mapping[str, Any]:
    bounds = {"fit": FIT_DAYS, "calibration": CALIBRATION_DAYS, "test": TEST_DAYS}
    result = {}
    for name, indices in splits.items():
        supervised = indices[rows.action_mask[indices]]
        result[name] = {"bounds": bounds[name], "rows": len(indices),
            "supervised_rows": len(supervised),
            "positives": int(rows.action[supervised].sum()),
            "per_asset": {asset: {
                "rows": int(sum(rows.assets[int(i)] == asset for i in indices)),
                "supervised_rows": int(sum(
                    rows.assets[int(i)] == asset for i in supervised)),
                "positives": int(sum(
                    rows.assets[int(i)] == asset and rows.action[int(i)]
                    for i in supervised)),
            } for asset in ASSETS}}
    return result


def decision_canary_sha256(model: nn.Module, calibrator: MonotonePlatt,
                           thresholds: Mapping[str, float]) -> str:
    return hashlib.sha256(C.canonical_bytes({"state": state_sha256(model),
        "platt": {"slope": calibrator.slope, "intercept": calibrator.intercept},
        "thresholds": dict(thresholds)})).hexdigest()


def _split_score_diagnostics(rows: ProbeRows, raw_logits: np.ndarray,
                             calibrated: np.ndarray) -> Mapping[str, Any]:
    raw_probability = 1.0 / (1.0 + np.exp(-np.clip(raw_logits, -50, 50)))
    def scope(indices: np.ndarray) -> Mapping[str, Any]:
        scoped = rows.take(indices)
        supervised = scoped.action_mask
        target = scoped.action[supervised]
        return {"rows": len(indices), "supervised_rows": int(supervised.sum()),
                "positives": int(target.sum()),
                "raw": binary_metrics(target, raw_probability[indices][supervised]),
                "calibrated": binary_metrics(target, calibrated[indices][supervised]),
                "topk": topk_metrics(scoped, calibrated[indices])}
    return {"global": scope(np.arange(len(rows.candidate_ids))),
            "by_asset": {asset: scope(np.flatnonzero(np.asarray(
                [value == asset for value in rows.assets]
            ))) for asset in ASSETS}}


def run_probe(path: str | Path = DEFAULT_FOLD, *, device: str | None = None,
              batch_size: int = 512) -> Mapping[str, Any]:
    """Run the production-sized diagnostic.  Call explicitly; never on import."""
    determinism = configure_determinism()
    requested_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    if requested_device == "cuda" and not torch.cuda.is_available():
        raise C.EntryV2Refusal("CUDA was requested but is unavailable")
    fold, original_rows = load_e3_rows(path)
    splits = split_rows(original_rows)
    rows, normalization = normalize_from_fit(original_rows, splits["fit"])
    selected_ids = tuple(candidate_id for candidate_id, selected in
                         zip(rows.candidate_ids, rows.action) if selected)
    supervised_ids = tuple(candidate_id for candidate_id, supervised in
                           zip(rows.candidate_ids, rows.action_mask) if supervised)
    truth_indices = splits["test"]
    truth_test = tuple(fold.truth_arrivals[int(i)] for i in truth_indices)
    truth_evaluation = replay(truth_test, expected_sessions=_sessions(fold, *TEST_DAYS))
    receipt: dict[str, Any] = {"schema": "entry-v2-e3-representation-probe-v1",
        "diagnostic_only": True, "seed": SEED, "fold": "E3", "control": "PROPHET",
        "fold_identity": {"fold": "E3", "control_name": "PROPHET",
            "fold_store_schema": FOLD_STORE_SCHEMA, "fold_oof_schema": FOLD_OOF_SCHEMA},
        "fold_store_aggregate_sha256": EXPECTED_AGGREGATE_SHA256,
        "device": requested_device, "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": (torch.cuda.get_device_name(0)
                             if requested_device == "cuda" else None),
        "torch_version": torch.__version__,
        "bf16": requested_device == "cuda",
        "determinism": determinism, "splits": _split_receipt(rows, splits),
        "identity": {"candidate_ids_sha256": _sha256_ids(rows.candidate_ids),
            "selected_ids_sha256": _sha256_ids(selected_ids),
            "action_supervised_ids_sha256": _sha256_ids(supervised_ids),
            "action_mask_sha256": _sha256_array(rows.action_mask),
            "days_sha256": _sha256_array(rows.days),
            "raw_embeddings_sha256": _sha256_array(original_rows.embeddings),
            "raw_static_features_sha256": _sha256_array(original_rows.static_features),
            "normalized_embeddings_sha256": _sha256_array(rows.embeddings),
            "normalized_static_features_sha256": _sha256_array(rows.static_features)},
        "normalization": normalization,
        "truth_control": _evaluation_receipt(truth_evaluation),
        "training_config": {"standard_epochs": 2, "hard_tail_epochs": 1,
            "batch_size": batch_size, "optimizer": "AdamW", "learning_rate": 2e-4,
            "weight_decay": 1e-2, "betas": (0.9, 0.999), "epsilon": 1e-8,
            "amsgrad": False, "adapter_seeds": ADAPTER_SEEDS,
            "head_seed": HEAD_SEED, "width": WIDTH, "memory_tokens_per_input": 4,
            "attention_heads": 8, "blocks": 2, "ffn_width": 2048, "dropout": 0.0},
        "loss_config": {"action": "masked BCE exact global fit neg/pos",
            "expected_value": "smooth-L1 / 1000", "top3": "BCE exact global fit neg/pos",
            "wall": "BCE exact global fit neg/pos", "mae": "q90 pinball / 900",
            "auxiliary_scope": "all fit rows", "component_coefficients": {
                "action": 1.0, "expected_value": 1.0, "top3": 1.0,
                "wall": 1.0, "mae": 1.0, "pairwise": 1.0},
            "reduction": "mean per chronological minibatch",
            "pairwise_margin": PAIRWISE_MARGIN},
        "results": {}}
    initial_head_hash: str | None = None
    for representation in ("embedding", "static", "late_fusion"):
        fit = rows.take(splits["fit"])
        loss_weights = LossWeights.from_fit(fit)
        models = train_models(fit, representation, batch_size=batch_size, device=device)
        receipt["results"][representation] = {}
        for objective, model in models.items():
            if initial_head_hash is None:
                initial_head_hash = model.initial_head_sha256
            elif model.initial_head_sha256 != initial_head_hash:
                raise C.EntryV2Refusal("shared probe heads did not initialize identically")
            split_logits = {name: predict_logits(
                model, rows.take(indices), next(model.parameters()).device, batch_size
            )["action"] for name, indices in splits.items()}
            cal_rows = rows.take(splits["calibration"])
            cal_supervised = cal_rows.action_mask
            calibrator = MonotonePlatt.fit(
                split_logits["calibration"][cal_supervised],
                cal_rows.action[cal_supervised].astype(float),
            )
            calibrated = {name: calibrator.predict(values)
                          for name, values in split_logits.items()}
            fit_calibration_diagnostics = {
                name: _split_score_diagnostics(
                    rows.take(splits[name]), split_logits[name], calibrated[name]
                ) for name in ("fit", "calibration")}
            thresholds, funnel = select_thresholds(
                fold, splits["calibration"], calibrated["calibration"]
            )
            test_arrivals = _scored_rows(
                fold, splits["test"], calibrated["test"], thresholds,
                f"e3-probe:{representation}:{objective}:{state_sha256(model)}"
            )
            test_eval = replay(test_arrivals, expected_sessions=_sessions(fold, *TEST_DAYS))
            test_rows = rows.take(splits["test"])
            by_asset = {}
            for asset in ASSETS:
                local = np.asarray([a == asset for a in test_rows.assets])
                supervised = local & test_rows.action_mask
                target = test_rows.action[supervised]
                raw_probability = 1 / (1 + np.exp(-np.clip(
                    split_logits["test"][supervised], -50, 50)))
                asset_eval = next(value for value in test_eval.by_asset if value.asset == asset)
                by_asset[asset] = {
                    "supervised_rows": int(supervised.sum()), "positives": int(target.sum()),
                    "raw": binary_metrics(target, raw_probability),
                    "calibrated": binary_metrics(target, calibrated["test"][supervised]),
                    "topk": topk_metrics(test_rows.take(np.flatnonzero(local)),
                                         calibrated["test"][local]),
                    "threshold": thresholds[asset], "calibration_funnel": funnel[asset],
                    # V4: never a bare $0/MDD:0 row -- the typed status of the
                    # threshold funnel travels with every published economic
                    # column so a consumer cannot read an empty book as a
                    # clean, zero-drawdown result.
                    "threshold_status": funnel[asset]["status"],
                    "economics_publishable":
                        funnel[asset]["economics_publishable"],
                    "test": {key: getattr(asset_eval, key) for key in (
                        "trades", "total_pnl_usd", "usd_per_asset_day",
                        "usd_per_trade", "max_drawdown_usd")},
                    "truth_control": receipt["truth_control"]["by_asset"][asset],
                }
            receipt["results"][representation][objective] = {
                "architecture": model.architecture_receipt(),
                "initial_head_sha256": model.initial_head_sha256,
                "initial_state_sha256": model.initial_state_sha256,
                "standard_checkpoint_sha256": model.standard_checkpoint_sha256,
                "tail_start_sha256": model.tail_start_sha256,
                "final_state_sha256": state_sha256(model),
                "epoch_full_fit_losses": model.training_history,
                "loss_weights": loss_weights.as_dict(), "platt": calibrator.__dict__,
                "thresholds": dict(thresholds),
                "decision_canary_sha256": decision_canary_sha256(
                    model, calibrator, thresholds),
                "assets": by_asset,
                "fit_calibration_diagnostics": fit_calibration_diagnostics,
                "global_topk": topk_metrics(test_rows, calibrated["test"]),
            }
    receipt["residual_late_fusion_minus_embedding"] = {
        objective: {asset: {
            metric: (receipt["results"]["late_fusion"][objective]["assets"][asset]
                     ["test"][metric]
                     - receipt["results"]["embedding"][objective]["assets"][asset]
                     ["test"][metric])
            for metric in ("trades", "total_pnl_usd", "usd_per_asset_day",
                           "usd_per_trade", "max_drawdown_usd")}
            for asset in ASSETS}
        for objective in ("standard", "tail_aware")}
    receipt["shared_initial_head_sha256"] = initial_head_hash
    receipt["receipt_sha256_law"] = "sha256(canonical JSON before receipt_sha256 field)"
    receipt["receipt_sha256"] = hashlib.sha256(C.canonical_bytes(receipt)).hexdigest()
    return receipt


def _write_receipt_atomic(output: str | Path, receipt: Mapping[str, Any]) -> None:
    target = C.assert_workspace_output(output)
    if target.exists():
        raise C.EntryV2Refusal(f"diagnostic output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    if temporary.exists():
        raise C.EntryV2Refusal(f"diagnostic temporary output exists: {temporary}")
    try:
        with open(temporary, "xb") as handle:
            handle.write(C.canonical_bytes(receipt))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o444)
        os.rename(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostic-only E3 representation probe")
    parser.add_argument("--fold", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", required=True, choices=("cpu", "cuda"))
    args = parser.parse_args(argv)
    receipt = run_probe(args.fold, device=args.device)
    _write_receipt_atomic(args.output, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
