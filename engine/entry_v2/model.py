#!/usr/bin/env python3
"""Causal full-prefix entry model.

This module deliberately owns no data loading and no policy thresholds.  Its
contract is smaller and easier to audit:

* ``candidate_cutoffs[i]`` is the number of source events whose ``ts_event`` is
  strictly before candidate ``i``;
* every candidate cutoff is a hard local-block boundary;
* a candidate is represented by the long-stream state at that boundary; and
* candidate geometry and slow context are fused only after that shared prefix
  state has been gathered.

Consequently, adding events after a cutoff cannot change that cutoff's state,
and two candidates at the same cutoff receive the exact same tape state.  The
model consumes continuous event values without clipping or bucketing; callers
are responsible for causal, train-fold normalization.  Categorical event
fields (normally action, side, and flags) retain their exact integer values and
are embedded independently.

The module is intentionally pure PyTorch.  PyTorch 2.8's native SDPA dispatches
to the fused CUDA implementation on the project GPU, so no third-party
attention package is required.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Optional, Sequence

import torch
from torch import Tensor, nn
import torch.nn.functional as F


LOCAL_WIDTH = 128
LOCAL_DEPTH = 2
LOCAL_HEADS = 4
N_BLOCK_SUMMARIES = 4
LONG_WIDTH = 512
LONG_DEPTH = 8
LONG_HEADS = 8
CONTEXT_WIDTH = 128
CONTEXT_DEPTH = 2
CONTEXT_HEADS = 4
N_ASSETS = 3
DEFAULT_BLOCK_SIZE = 256


class EntryModelRefusal(ValueError):
    """An input violates the causal model contract."""


@dataclass(frozen=True)
class BlockPartition:
    """Contiguous event blocks and the candidate-to-prefix mapping.

    ``candidate_block`` is ``-1`` for a cutoff at session open and otherwise
    indexes the unique block whose ``stop`` equals that candidate cutoff.
    Candidate order is preserved, including duplicate cutoffs.
    """

    starts: Tensor
    stops: Tensor
    lengths: Tensor
    candidate_block: Tensor
    unique_cutoffs: Tensor
    block_size: int

    @property
    def n_blocks(self) -> int:
        return int(self.starts.numel())


@dataclass
class EntryModelOutput:
    """Candidate-grain outputs.

    ``embedding`` is the stable representation intended for an out-of-fold,
    deterministic per-asset GBT.  Auxiliary heads remain explicit so training
    cannot silently collapse back to a single ranking objective.
    """

    embedding: Tensor
    prefix_state: Tensor
    context_state: Tensor
    value_bin_logits: Tensor
    value_quantiles: Tensor
    expected_value: Tensor
    top3_logit: Tensor
    mae_quantiles: Tensor
    wall_logit: Tensor
    take_logit: Tensor
    partition: BlockPartition


def _require_integer(name: str, value: Tensor) -> None:
    if value.dtype not in (
        torch.int8,
        torch.int16,
        torch.int32,
        torch.int64,
        torch.uint8,
    ):
        raise EntryModelRefusal(f"{name} must be an integer tensor, got {value.dtype}")


def partition_event_blocks(
    n_events: int,
    candidate_cutoffs: Tensor,
    block_size: int = DEFAULT_BLOCK_SIZE,
) -> BlockPartition:
    """Partition a session without allowing a block to cross a cutoff.

    Boundaries are the union of ``{0, n_events}``, every positive multiple of
    ``block_size`` below ``n_events``, and every unique candidate cutoff.  The
    operation is device-preserving and candidate order is not changed.
    """

    n_events = int(n_events)
    block_size = int(block_size)
    if n_events < 0:
        raise EntryModelRefusal(f"n_events must be non-negative, got {n_events}")
    if block_size <= 0:
        raise EntryModelRefusal(f"block_size must be positive, got {block_size}")
    if candidate_cutoffs.ndim != 1:
        raise EntryModelRefusal(
            f"candidate_cutoffs must be rank 1, got {tuple(candidate_cutoffs.shape)}"
        )
    _require_integer("candidate_cutoffs", candidate_cutoffs)
    cutoffs = candidate_cutoffs.to(dtype=torch.int64)
    if cutoffs.numel():
        lo = int(cutoffs.min().item())
        hi = int(cutoffs.max().item())
        if lo < 0 or hi > n_events:
            raise EntryModelRefusal(
                f"candidate cutoff outside [0, {n_events}]: min={lo}, max={hi}"
            )

    device = cutoffs.device
    regular = (
        torch.arange(
            block_size, n_events, block_size, dtype=torch.int64, device=device
        )
        if n_events > block_size
        else torch.empty(0, dtype=torch.int64, device=device)
    )
    ends = torch.tensor([0, n_events], dtype=torch.int64, device=device)
    boundaries = torch.unique(torch.cat((ends, regular, cutoffs)), sorted=True)
    starts = boundaries[:-1]
    stops = boundaries[1:]
    lengths = stops - starts

    if lengths.numel() and bool((lengths <= 0).any().item()):
        raise EntryModelRefusal("partition constructed an empty or inverted block")
    if lengths.numel() and int(lengths.max().item()) > block_size:
        raise EntryModelRefusal("partition constructed a block larger than block_size")

    candidate_block = torch.full_like(cutoffs, -1)
    positive = cutoffs > 0
    if bool(positive.any().item()):
        where = torch.searchsorted(stops, cutoffs[positive], right=False)
        if bool((where >= stops.numel()).any().item()) or not torch.equal(
            stops[where], cutoffs[positive]
        ):
            raise EntryModelRefusal("candidate cutoff is not a partition boundary")
        candidate_block[positive] = where

    return BlockPartition(
        starts=starts,
        stops=stops,
        lengths=lengths,
        candidate_block=candidate_block,
        unique_cutoffs=torch.unique(cutoffs, sorted=True),
        block_size=block_size,
    )


def _sinusoidal_positions(length: int, width: int, device: torch.device) -> Tensor:
    """Length-independent positional encoding in float32.

    Earlier rows are bit-identical when a sequence is extended, unlike a
    position scheme whose scale depends on the final sequence length.
    """

    if length == 0:
        return torch.empty((0, width), dtype=torch.float32, device=device)
    position = torch.arange(length, dtype=torch.float32, device=device)[:, None]
    div = torch.exp(
        torch.arange(0, width, 2, dtype=torch.float32, device=device)
        * (-math.log(10_000.0) / width)
    )
    out = torch.zeros((length, width), dtype=torch.float32, device=device)
    out[:, 0::2] = torch.sin(position * div)
    out[:, 1::2] = torch.cos(position * div)
    return out


class SDPAEncoderBlock(nn.Module):
    """Pre-norm transformer block using native scaled-dot-product attention."""

    def __init__(
        self,
        width: int,
        heads: int,
        ffn_width: int,
        *,
        causal: bool,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        if width % heads:
            raise ValueError(f"width {width} is not divisible by heads {heads}")
        self.width = int(width)
        self.heads = int(heads)
        self.head_width = self.width // self.heads
        self.causal = bool(causal)
        self.dropout = float(dropout)
        self.norm1 = nn.LayerNorm(width)
        self.qkv = nn.Linear(width, 3 * width)
        self.attn_out = nn.Linear(width, width)
        self.norm2 = nn.LayerNorm(width)
        self.ff1 = nn.Linear(width, ffn_width)
        self.ff2 = nn.Linear(ffn_width, width)

    def forward(self, x: Tensor, key_mask: Optional[Tensor] = None) -> Tensor:
        batch, steps, width = x.shape
        h = self.norm1(x)
        q, k, v = self.qkv(h).chunk(3, dim=-1)

        def split_heads(value: Tensor) -> Tensor:
            return value.view(batch, steps, self.heads, self.head_width).transpose(1, 2)

        q, k, v = split_heads(q), split_heads(k), split_heads(v)
        attn_mask = None
        if key_mask is not None:
            if self.causal:
                raise EntryModelRefusal(
                    "a key mask and causal mask are not combined in this block; "
                    "causal callers must right-pad so valid queries precede padding"
                )
            if key_mask.shape != (batch, steps):
                raise EntryModelRefusal(
                    f"key_mask must be {(batch, steps)}, got {tuple(key_mask.shape)}"
                )
            attn_mask = key_mask[:, None, None, :].to(dtype=torch.bool)
        h = F.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=attn_mask,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=self.causal,
        )
        h = h.transpose(1, 2).contiguous().view(batch, steps, width)
        x = x + self.attn_out(h)
        h = self.ff2(F.gelu(self.ff1(self.norm2(x))))
        return x + h


class LearnedQueryPool(nn.Module):
    """Multi-head learned queries over a masked sequence."""

    def __init__(self, width: int, heads: int, n_queries: int) -> None:
        super().__init__()
        if width % heads:
            raise ValueError(f"width {width} is not divisible by heads {heads}")
        self.width = int(width)
        self.heads = int(heads)
        self.head_width = self.width // self.heads
        self.n_queries = int(n_queries)
        self.query = nn.Parameter(torch.empty(n_queries, width))
        self.q_proj = nn.Linear(width, width)
        self.k_proj = nn.Linear(width, width)
        self.v_proj = nn.Linear(width, width)
        self.out = nn.Linear(width, width)
        nn.init.trunc_normal_(self.query, std=0.02)

    def forward(self, x: Tensor, valid: Tensor) -> Tensor:
        batch, steps, width = x.shape
        if valid.shape != (batch, steps):
            raise EntryModelRefusal(
                f"pool mask must be {(batch, steps)}, got {tuple(valid.shape)}"
            )
        if bool((valid.sum(dim=1) == 0).any().item()):
            raise EntryModelRefusal("LearnedQueryPool received an empty sequence")
        q = self.q_proj(self.query).view(
            1, self.n_queries, self.heads, self.head_width
        )
        q = q.expand(batch, -1, -1, -1).transpose(1, 2)

        def split_heads(value: Tensor) -> Tensor:
            return value.view(batch, steps, self.heads, self.head_width).transpose(1, 2)

        k = split_heads(self.k_proj(x))
        v = split_heads(self.v_proj(x))
        h = F.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=valid[:, None, None, :].to(dtype=torch.bool),
            dropout_p=0.0,
            is_causal=False,
        )
        h = h.transpose(1, 2).contiguous().view(batch, self.n_queries, width)
        return self.out(h)


class LocalEventEncoder(nn.Module):
    """Exact event fields -> four causal block summaries."""

    def __init__(
        self,
        n_continuous: int,
        category_sizes: Sequence[int],
        *,
        block_size: int = DEFAULT_BLOCK_SIZE,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        if n_continuous <= 0:
            raise ValueError("n_continuous must be positive")
        if not category_sizes or any(int(x) <= 0 for x in category_sizes):
            raise ValueError("category_sizes must contain positive cardinalities")
        self.n_continuous = int(n_continuous)
        self.category_sizes = tuple(int(x) for x in category_sizes)
        self.block_size = int(block_size)
        self.continuous_projection = nn.Linear(n_continuous, LOCAL_WIDTH)
        self.category_embeddings = nn.ModuleList(
            nn.Embedding(size, LOCAL_WIDTH) for size in self.category_sizes
        )
        self.local_position = nn.Parameter(torch.empty(block_size, LOCAL_WIDTH))
        nn.init.trunc_normal_(self.local_position, std=0.02)
        self.layers = nn.ModuleList(
            SDPAEncoderBlock(
                LOCAL_WIDTH,
                LOCAL_HEADS,
                4 * LOCAL_WIDTH,
                causal=True,
                dropout=dropout,
            )
            for _ in range(LOCAL_DEPTH)
        )
        self.norm = nn.LayerNorm(LOCAL_WIDTH)
        self.pool = LearnedQueryPool(LOCAL_WIDTH, LOCAL_HEADS, N_BLOCK_SUMMARIES)
        self.to_long = nn.Linear(LOCAL_WIDTH, LONG_WIDTH)
        self.summary_type = nn.Parameter(torch.empty(N_BLOCK_SUMMARIES, LONG_WIDTH))
        nn.init.trunc_normal_(self.summary_type, std=0.02)

    def _pack(
        self,
        continuous: Tensor,
        categorical: Tensor,
        partition: BlockPartition,
    ) -> tuple[Tensor, Tensor, Tensor]:
        n_blocks = partition.n_blocks
        if n_blocks == 0:
            return (
                continuous.new_zeros((0, self.block_size, self.n_continuous)),
                categorical.new_zeros(
                    (0, self.block_size, len(self.category_sizes)),
                    dtype=torch.long,
                ),
                torch.zeros(
                    (0, self.block_size), dtype=torch.bool, device=continuous.device
                ),
            )
        offset = torch.arange(
            self.block_size, dtype=torch.int64, device=continuous.device
        )[None, :]
        event_index = partition.starts[:, None] + offset
        valid = event_index < partition.stops[:, None]
        safe_index = event_index.clamp(max=max(int(continuous.shape[0]) - 1, 0))
        packed_continuous = continuous[safe_index]
        packed_categorical = categorical[safe_index].to(dtype=torch.long)
        packed_continuous = packed_continuous * valid[..., None].to(
            dtype=packed_continuous.dtype
        )
        packed_categorical = torch.where(
            valid[..., None], packed_categorical, torch.zeros_like(packed_categorical)
        )
        return packed_continuous, packed_categorical, valid

    def forward(
        self,
        continuous: Tensor,
        categorical: Tensor,
        partition: BlockPartition,
    ) -> Tensor:
        if continuous.ndim != 2 or continuous.shape[1] != self.n_continuous:
            raise EntryModelRefusal(
                "event_continuous must have shape "
                f"[events, {self.n_continuous}], got {tuple(continuous.shape)}"
            )
        if not continuous.is_floating_point():
            raise EntryModelRefusal("event_continuous must be floating point")
        if categorical.ndim != 2 or categorical.shape != (
            continuous.shape[0],
            len(self.category_sizes),
        ):
            raise EntryModelRefusal(
                "event_categorical must have shape "
                f"[{continuous.shape[0]}, {len(self.category_sizes)}], got "
                f"{tuple(categorical.shape)}"
            )
        _require_integer("event_categorical", categorical)
        if partition.n_blocks == 0:
            return continuous.new_zeros((0, N_BLOCK_SUMMARIES, LONG_WIDTH))
        packed_continuous, packed_categorical, valid = self._pack(
            continuous, categorical, partition
        )
        h = self.continuous_projection(packed_continuous)
        for column, (embedding, cardinality) in enumerate(
            zip(self.category_embeddings, self.category_sizes)
        ):
            ids = packed_categorical[..., column]
            if ids.numel():
                lo, hi = int(ids.min().item()), int(ids.max().item())
                if lo < 0 or hi >= cardinality:
                    raise EntryModelRefusal(
                        f"categorical column {column} outside [0, {cardinality}): "
                        f"min={lo}, max={hi}"
                    )
            h = h + embedding(ids)
        h = h + self.local_position[None, :, :].to(dtype=h.dtype)
        h = h * valid[..., None].to(dtype=h.dtype)
        for layer in self.layers:
            h = layer(h)
            h = h * valid[..., None].to(dtype=h.dtype)
        h = self.norm(h)
        summary = self.to_long(self.pool(h, valid))
        return summary + self.summary_type[None, :, :].to(dtype=summary.dtype)


class TypedContextEncoder(nn.Module):
    """Two-layer typed encoder over released slow-context histories.

    Histories are encoded independently per series, then the series states are
    pooled.  ``type_ids`` prevents values from different economic series from
    becoming interchangeable.  Missing/revised series should arrive with a
    false mask from the causal context packer.
    """

    def __init__(
        self,
        n_continuous: int,
        n_types: int,
        *,
        max_history: int = 64,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        if n_continuous <= 0 or n_types <= 0 or max_history <= 0:
            raise ValueError("context dimensions and cardinalities must be positive")
        self.n_continuous = int(n_continuous)
        self.n_types = int(n_types)
        self.max_history = int(max_history)
        self.value_projection = nn.Linear(n_continuous, CONTEXT_WIDTH)
        self.type_embedding = nn.Embedding(n_types, CONTEXT_WIDTH)
        self.history_position = nn.Parameter(
            torch.empty(max_history, CONTEXT_WIDTH)
        )
        nn.init.trunc_normal_(self.history_position, std=0.02)
        self.layers = nn.ModuleList(
            SDPAEncoderBlock(
                CONTEXT_WIDTH,
                CONTEXT_HEADS,
                4 * CONTEXT_WIDTH,
                causal=False,
                dropout=dropout,
            )
            for _ in range(CONTEXT_DEPTH)
        )
        self.norm = nn.LayerNorm(CONTEXT_WIDTH)
        self.series_pool = LearnedQueryPool(CONTEXT_WIDTH, CONTEXT_HEADS, 1)

    def forward(self, values: Tensor, type_ids: Tensor, valid: Tensor) -> Tensor:
        if values.ndim != 4 or values.shape[-1] != self.n_continuous:
            raise EntryModelRefusal(
                "context_values must have shape "
                f"[candidates, series, history, {self.n_continuous}], got "
                f"{tuple(values.shape)}"
            )
        candidates, n_series, history, _ = values.shape
        if history > self.max_history:
            raise EntryModelRefusal(
                f"context history {history} exceeds maximum {self.max_history}"
            )
        if valid.shape != (candidates, n_series, history):
            raise EntryModelRefusal(
                f"context_valid must be {(candidates, n_series, history)}, got "
                f"{tuple(valid.shape)}"
            )
        if type_ids.ndim == 1:
            if type_ids.shape[0] != n_series:
                raise EntryModelRefusal(
                    f"context_type_ids must have {n_series} elements"
                )
            type_ids = type_ids[None, :].expand(candidates, -1)
        if type_ids.shape != (candidates, n_series):
            raise EntryModelRefusal(
                f"context_type_ids must be {(candidates, n_series)}, got "
                f"{tuple(type_ids.shape)}"
            )
        _require_integer("context_type_ids", type_ids)
        type_ids = type_ids.to(dtype=torch.long)
        if type_ids.numel():
            lo, hi = int(type_ids.min().item()), int(type_ids.max().item())
            if lo < 0 or hi >= self.n_types:
                raise EntryModelRefusal(
                    f"context type outside [0, {self.n_types}): min={lo}, max={hi}"
                )
        if candidates == 0:
            return values.new_zeros((0, CONTEXT_WIDTH))
        if n_series == 0 or history == 0:
            return values.new_zeros((candidates, CONTEXT_WIDTH))

        valid = valid.to(dtype=torch.bool)
        h = self.value_projection(values)
        h = h + self.type_embedding(type_ids)[:, :, None, :]
        h = h + self.history_position[None, None, :history, :].to(dtype=h.dtype)
        h = h * valid[..., None].to(dtype=h.dtype)
        h = h.view(candidates * n_series, history, CONTEXT_WIDTH)
        mask = valid.view(candidates * n_series, history)
        series_valid = mask.any(dim=1)
        safe_mask = mask.clone()
        safe_mask[~series_valid, 0] = True
        for layer in self.layers:
            h = layer(h, safe_mask)
            h = h * safe_mask[..., None].to(dtype=h.dtype)
        h = self.norm(h)
        weights = mask.to(dtype=h.dtype)
        series_state = (h * weights[..., None]).sum(dim=1) / weights.sum(
            dim=1, keepdim=True
        ).clamp_min(1.0)
        series_state = series_state * series_valid[:, None].to(dtype=h.dtype)
        series_state = series_state.view(candidates, n_series, CONTEXT_WIDTH)

        candidate_has_context = series_valid.view(candidates, n_series).any(dim=1)
        series_mask = series_valid.view(candidates, n_series)
        safe_series_mask = series_mask.clone()
        safe_series_mask[~candidate_has_context, 0] = True
        pooled = self.series_pool(series_state, safe_series_mask)[:, 0, :]
        return pooled * candidate_has_context[:, None].to(dtype=pooled.dtype)


class AssetAdapter(nn.Module):
    """Small residual expert; one independently parameterized adapter/asset."""

    def __init__(self, width: int = LONG_WIDTH, bottleneck: int = 64) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(width)
        self.down = nn.Linear(width, bottleneck)
        self.up = nn.Linear(bottleneck, width)
        # A new adapter starts as an identity, avoiding arbitrary asset skew.
        nn.init.zeros_(self.up.weight)
        nn.init.zeros_(self.up.bias)

    def forward(self, x: Tensor) -> Tensor:
        return x + self.up(F.gelu(self.down(self.norm(x))))


class FullPrefixEntryModel(nn.Module):
    """Fixed hierarchical full-prefix architecture."""

    def __init__(
        self,
        n_event_continuous: int,
        n_candidate_features: int,
        n_context_continuous: int,
        n_context_types: int,
        *,
        # QRE2EVT2 exposes action, side, flags, depth, and the three-bit
        # price-undefined mask.  Synthetic tests may override this tuple, but the
        # production-safe default must match EventPack.CATEGORICAL_FIELDS.
        event_category_sizes: Sequence[int] = (256, 256, 256, 256, 8),
        n_value_bins: int = 5,
        block_size: int = DEFAULT_BLOCK_SIZE,
        max_context_history: int = 64,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        if n_candidate_features <= 0 or n_value_bins <= 1:
            raise ValueError("candidate feature count and value-bin count are invalid")
        self.n_event_continuous = int(n_event_continuous)
        self.n_candidate_features = int(n_candidate_features)
        self.n_context_continuous = int(n_context_continuous)
        self.n_context_types = int(n_context_types)
        self.n_value_bins = int(n_value_bins)
        self.block_size = int(block_size)
        self.event_category_sizes = tuple(int(x) for x in event_category_sizes)

        self.local = LocalEventEncoder(
            n_event_continuous,
            self.event_category_sizes,
            block_size=block_size,
            dropout=dropout,
        )
        self.session_bos = nn.Parameter(torch.empty(LONG_WIDTH))
        nn.init.trunc_normal_(self.session_bos, std=0.02)
        self.long_layers = nn.ModuleList(
            SDPAEncoderBlock(
                LONG_WIDTH,
                LONG_HEADS,
                4 * LONG_WIDTH,
                causal=True,
                dropout=dropout,
            )
            for _ in range(LONG_DEPTH)
        )
        self.long_norm = nn.LayerNorm(LONG_WIDTH)
        self.asset_adapters = nn.ModuleList(AssetAdapter() for _ in range(N_ASSETS))

        self.context = TypedContextEncoder(
            n_context_continuous,
            n_context_types,
            max_history=max_context_history,
            dropout=dropout,
        )
        self.geometry = nn.Sequential(
            nn.Linear(n_candidate_features, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Linear(256, 256),
            nn.GELU(),
        )
        self.fusion = nn.Sequential(
            nn.Linear(LONG_WIDTH + 256 + CONTEXT_WIDTH, LONG_WIDTH),
            nn.LayerNorm(LONG_WIDTH),
            nn.GELU(),
            nn.Linear(LONG_WIDTH, LONG_WIDTH),
            nn.GELU(),
        )

        self.value_bin_head = nn.Linear(LONG_WIDTH, n_value_bins)
        self.value_quantile_head = nn.Linear(LONG_WIDTH, 3)
        self.expected_value_head = nn.Linear(LONG_WIDTH, 1)
        self.top3_head = nn.Linear(LONG_WIDTH, 1)
        self.mae_quantile_head = nn.Linear(LONG_WIDTH, 3)
        self.wall_head = nn.Linear(LONG_WIDTH, 1)
        self.take_head = nn.Linear(LONG_WIDTH, 1)

    def architecture(self) -> dict[str, object]:
        """Machine-readable frozen architecture receipt."""

        return {
            "event_continuous": self.n_event_continuous,
            "event_category_sizes": list(self.event_category_sizes),
            "block_size": self.block_size,
            "local": {
                "width": LOCAL_WIDTH,
                "depth": LOCAL_DEPTH,
                "heads": LOCAL_HEADS,
                "summaries_per_block": N_BLOCK_SUMMARIES,
            },
            "long": {
                "width": LONG_WIDTH,
                "depth": LONG_DEPTH,
                "heads": LONG_HEADS,
            },
            "context": {
                "continuous": self.n_context_continuous,
                "types": self.n_context_types,
                "width": CONTEXT_WIDTH,
                "depth": CONTEXT_DEPTH,
                "heads": CONTEXT_HEADS,
            },
            "assets": N_ASSETS,
            "candidate_features": self.n_candidate_features,
            "value_bins": self.n_value_bins,
        }

    def _prefix_states(
        self,
        event_continuous: Tensor,
        event_categorical: Tensor,
        partition: BlockPartition,
        asset_idx: int,
    ) -> Tensor:
        candidate_block = partition.candidate_block
        candidates = int(candidate_block.numel())
        if partition.n_blocks:
            summary = self.local(event_continuous, event_categorical, partition)
            long = summary.reshape(1, partition.n_blocks * N_BLOCK_SUMMARIES, LONG_WIDTH)
            pos = _sinusoidal_positions(long.shape[1], LONG_WIDTH, long.device)
            long = long + pos[None, :, :].to(dtype=long.dtype)
            for layer in self.long_layers:
                long = layer(long)
            long = self.long_norm(long)
            block_state = long.view(
                partition.n_blocks, N_BLOCK_SUMMARIES, LONG_WIDTH
            ).mean(dim=1)
        else:
            block_state = event_continuous.new_zeros((0, LONG_WIDTH))

        prefix = self.session_bos[None, :].expand(candidates, -1).clone()
        has_events = candidate_block >= 0
        if bool(has_events.any().item()):
            prefix[has_events] = block_state[candidate_block[has_events]]
        return self.asset_adapters[asset_idx](prefix)

    def forward(
        self,
        *,
        event_continuous: Tensor,
        event_categorical: Tensor,
        candidate_cutoffs: Tensor,
        candidate_features: Tensor,
        context_values: Tensor,
        context_type_ids: Tensor,
        context_valid: Tensor,
        asset_idx: int,
    ) -> EntryModelOutput:
        asset_idx = int(asset_idx)
        if not 0 <= asset_idx < N_ASSETS:
            raise EntryModelRefusal(f"asset_idx must be in [0, {N_ASSETS}), got {asset_idx}")
        if event_continuous.device != candidate_cutoffs.device:
            raise EntryModelRefusal("events and candidate_cutoffs must be on one device")
        if event_categorical.device != event_continuous.device:
            raise EntryModelRefusal("continuous and categorical events must be on one device")
        if event_categorical.ndim != 2 or event_categorical.shape[0] != event_continuous.shape[0]:
            raise EntryModelRefusal("continuous and categorical event counts do not match")
        candidates = int(candidate_cutoffs.numel())
        if candidate_features.shape != (candidates, self.n_candidate_features):
            raise EntryModelRefusal(
                f"candidate_features must be {(candidates, self.n_candidate_features)}, "
                f"got {tuple(candidate_features.shape)}"
            )
        if candidate_features.device != event_continuous.device:
            raise EntryModelRefusal("candidate features and events must be on one device")
        if context_values.shape[0] != candidates:
            raise EntryModelRefusal("context candidate axis does not match cutoffs")
        if (
            context_values.device != event_continuous.device
            or context_type_ids.device != event_continuous.device
            or context_valid.device != event_continuous.device
        ):
            raise EntryModelRefusal("events, candidates, and context must be on one device")

        # Nothing beyond the latest requested cutoff is an input to this batch.
        # Apart from avoiding wasted work, this makes suffix independence exact:
        # appending arbitrary events after the last candidate cannot even change
        # the shapes seen by an attention kernel.
        if candidates:
            _require_integer("candidate_cutoffs", candidate_cutoffs)
            min_cutoff = int(candidate_cutoffs.min().item())
            visible_events = int(candidate_cutoffs.max().item())
            if min_cutoff < 0 or visible_events > int(event_continuous.shape[0]):
                raise EntryModelRefusal(
                    "candidate cutoff outside available event prefix: "
                    f"min={min_cutoff}, max={visible_events}, "
                    f"events={event_continuous.shape[0]}"
                )
        else:
            visible_events = 0

        partition = partition_event_blocks(
            visible_events, candidate_cutoffs, self.block_size
        )
        prefix = self._prefix_states(
            event_continuous[:visible_events],
            event_categorical[:visible_events],
            partition,
            asset_idx,
        )
        context = self.context(context_values, context_type_ids, context_valid)
        geometry = self.geometry(candidate_features)
        embedding = self.fusion(torch.cat((prefix, geometry, context), dim=-1))

        return EntryModelOutput(
            embedding=embedding,
            prefix_state=prefix,
            context_state=context,
            value_bin_logits=self.value_bin_head(embedding),
            value_quantiles=self.value_quantile_head(embedding),
            expected_value=self.expected_value_head(embedding).squeeze(-1),
            top3_logit=self.top3_head(embedding).squeeze(-1),
            mae_quantiles=self.mae_quantile_head(embedding),
            wall_logit=self.wall_head(embedding).squeeze(-1),
            take_logit=self.take_head(embedding).squeeze(-1),
            partition=partition,
        )


def model_state_sha256(model: nn.Module) -> str:
    """Hash names, shapes, dtypes, and exact parameter/buffer bytes."""

    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        cpu = value.detach().contiguous().cpu()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(tuple(cpu.shape)).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(cpu.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(cpu.reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


__all__ = [
    "BlockPartition",
    "EntryModelOutput",
    "EntryModelRefusal",
    "FullPrefixEntryModel",
    "partition_event_blocks",
    "model_state_sha256",
]
