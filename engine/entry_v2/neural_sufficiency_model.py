#!/usr/bin/env python3
"""Auditable model plane for the Entry-V2 neural-sufficiency diagnostic.

Raw encoders have an exact two-stage contract: encode a visible session once,
then gather bounded candidate memories.  Exact int64 receive clocks and
decision clocks prove every supplied cutoff using left ``searchsorted``.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Callable, Mapping, Optional, Sequence

import numpy as np
import torch
from torch import Tensor, nn
import torch.nn.functional as F
from torch.nn.utils.rnn import pack_padded_sequence
from torch.utils.checkpoint import checkpoint

from .model import (
    AssetAdapter, EntryModelRefusal, FullPrefixEntryModel, LearnedQueryPool,
    SDPAEncoderBlock, TypedContextEncoder, _sinusoidal_positions,
    partition_event_blocks,
)
from .diagnostic_inputs import frozen_chronology_split


MEMORY_TOKENS = 4
MODEL_WIDTH = 512
LOCAL_WIDTH = 128
STATIC_FEATURES = 1_865
STATIC_PADDED = 2_048
STATIC_TOKENS = 4
DEFAULT_HORIZONS = (300, 600, 900, 1_200, 1_800, -1)
CANONICAL_ARMS = ("C0", "C1", "L0", "L1", "M1")
DEVELOPMENT_CUTOFF_NS = 1_751_320_800_000_000_000


@dataclass(frozen=True)
class EventFieldSchema:
    continuous_fields: tuple[str, ...]
    categorical_fields: tuple[str, ...]
    category_sizes: tuple[int, ...]
    conversion_law_sha256: str
    synthetic: bool = False

    def __post_init__(self) -> None:
        if (not self.continuous_fields or not self.categorical_fields or
                len(self.categorical_fields) != len(self.category_sizes)):
            raise ValueError("event field schema is incomplete")
        names = self.continuous_fields + self.categorical_fields
        if len(set(names)) != len(names) or any(not x for x in names):
            raise ValueError("event field names must be unique and nonempty")
        if any(int(x) <= 0 for x in self.category_sizes):
            raise ValueError("categorical cardinalities must be positive")
        if not self.synthetic:
            continuous = set(self.continuous_fields)
            derived = {name for name in continuous
                       if name.startswith("derived.") and not name.endswith(".valid")}
            validity = {name.removesuffix(".valid") for name in continuous
                        if name.startswith("derived.") and name.endswith(".valid")}
            if derived != validity:
                raise ValueError(
                    "expanded derived fields must carry one explicit validity route"
                )
        if (len(self.conversion_law_sha256) != 64 or any(
                char not in "0123456789abcdef" for char in self.conversion_law_sha256)):
            raise ValueError("conversion_law_sha256 must be a 64-character digest")

    def canonical_bytes(self) -> bytes:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True).encode("ascii")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def generic_event_schema(n_continuous: int,
                         category_sizes: Sequence[int]) -> EventFieldSchema:
    body = {
        "continuous": [f"continuous_{i}" for i in range(int(n_continuous))],
        "categorical": [f"categorical_{i}" for i in range(len(category_sizes))],
        "category_sizes": [int(x) for x in category_sizes],
        "conversion": "caller_supplied_exact_normalized_values",
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True,
                                       separators=(",", ":")).encode()).hexdigest()
    return EventFieldSchema(tuple(body["continuous"]), tuple(body["categorical"]),
                            tuple(body["category_sizes"]), digest, True)


@dataclass(frozen=True)
class EncoderComplexityReceipt:
    events_visible: int
    regular_blocks: int
    candidates: int
    recent_window_events: int
    partial_block_events: int
    band_60_blocks: int
    band_300_blocks: int
    band_900_blocks: int
    regular_block_encodes: int
    regular_block_chunks: int = 0
    regular_block_chunk_high_water: int = 0
    candidate_window_chunks: int = 0
    candidate_window_chunk_high_water: int = 0
    unique_prefixes: int = 0
    repeated_prefixes_reused: int = 0
    law: tuple[str, ...] = (
        "local=O(N+256C);regular_blocks_chunked<=64;training_checkpointed",
        "full_gru=O(B+C)",
        "bands=O(W60+W300+W900)", "head=O(C)",
    )


@dataclass(frozen=True)
class M1SessionCache:
    continuous: Tensor
    categorical: Tensor
    receive_clock_ns: Tensor
    visible_events: int
    regular_summaries: Tensor
    regular_end_clock_ns: Tensor
    full_prefix_states: Tensor
    schema_sha256: str


def _integer(name: str, value: Tensor) -> None:
    if value.dtype not in (torch.uint8, torch.int8, torch.int16, torch.int32,
                            torch.int64):
        raise EntryModelRefusal(f"{name} must be integer")


def _activation_dtype(reference: Tensor) -> torch.dtype:
    """Return the declared autocast activation dtype for device-local work buffers."""
    device_type = reference.device.type
    if torch.is_autocast_enabled(device_type):
        return torch.get_autocast_dtype(device_type)
    return reference.dtype


def _activation_zeros(reference: Tensor, shape: Sequence[int]) -> Tensor:
    return torch.zeros(tuple(int(x) for x in shape), device=reference.device,
                       dtype=_activation_dtype(reference))


def _validate_exact_inputs(
    continuous: Tensor, categorical: Tensor, receive_clock_ns: Tensor,
    candidate_cutoffs: Tensor, candidate_decision_ts_ns: Tensor,
    schema: EventFieldSchema,
) -> tuple[Tensor, Tensor, int]:
    if continuous.ndim != 2 or continuous.shape[1] != len(schema.continuous_fields):
        raise EntryModelRefusal("event_continuous does not match the bound schema")
    if not continuous.is_floating_point():
        raise EntryModelRefusal("event_continuous must be floating point")
    if categorical.ndim != 2 or categorical.shape != (
        continuous.shape[0], len(schema.categorical_fields)
    ):
        raise EntryModelRefusal("event_categorical does not match the bound schema")
    _integer("event_categorical", categorical)
    if receive_clock_ns.dtype != torch.int64 or receive_clock_ns.shape != (
        continuous.shape[0],
    ):
        raise EntryModelRefusal("receive_clock_ns must be exact int64 [events]")
    if candidate_decision_ts_ns.dtype != torch.int64 or candidate_decision_ts_ns.ndim != 1:
        raise EntryModelRefusal("candidate_decision_ts_ns must be exact int64 [candidates]")
    if candidate_cutoffs.ndim != 1:
        raise EntryModelRefusal("candidate_cutoffs must be rank one")
    _integer("candidate_cutoffs", candidate_cutoffs)
    cutoffs = candidate_cutoffs.to(device=receive_clock_ns.device, dtype=torch.long)
    decisions = candidate_decision_ts_ns.to(device=receive_clock_ns.device)
    if cutoffs.shape != decisions.shape:
        raise EntryModelRefusal("candidate cutoff/decision counts differ")
    if continuous.device != categorical.device or continuous.device != receive_clock_ns.device:
        raise EntryModelRefusal("event values and exact clocks must share one device")
    if cutoffs.numel() and (int(cutoffs.min()) < 0
                            or int(cutoffs.max()) > continuous.shape[0]):
        raise EntryModelRefusal("candidate cutoff outside the event array")
    if decisions.numel() and (int(decisions.min()) < 0
                              or int(decisions.max()) >= DEVELOPMENT_CUTOFF_NS):
        raise EntryModelRefusal("candidate decision crosses the development wall")
    visible = int(cutoffs.max().item()) if cutoffs.numel() else 0
    visible_clock = receive_clock_ns[:visible]
    if visible_clock.numel() > 1 and bool(
        (visible_clock[1:] < visible_clock[:-1]).any()
    ):
        raise EntryModelRefusal("visible receive_clock_ns must be nondecreasing")
    # The model plane proves the complete visible prefix without consulting an
    # unavailable event payload.  For the maximum cutoff, lower_bound over the
    # visible clock returns len(prefix); smaller cutoffs are proved exactly.
    expected = torch.searchsorted(visible_clock, decisions, right=False)
    if not torch.equal(cutoffs, expected):
        raise EntryModelRefusal(
            "candidate_cutoffs must equal lower_bound(receive_clock_ns,decision); "
            "equal-time rows are future"
        )
    # Content validation deliberately stops at max cutoff.  Unavailable suffix
    # payload is not part of the model contract.
    visible_cat = categorical[:visible].to(dtype=torch.long)
    for field, size in enumerate(schema.category_sizes):
        if visible_cat.numel() and (int(visible_cat[:, field].min()) < 0 or
                int(visible_cat[:, field].max()) >= size):
            raise EntryModelRefusal(f"visible categorical field {field} is out of range")
    if not bool(torch.isfinite(continuous[:visible]).all()):
        raise EntryModelRefusal("visible continuous prefix contains non-finite values")
    return cutoffs, decisions, visible


class FieldPreservingStem(nn.Module):
    """Independent typed/gated route for every continuous and categorical field."""

    def __init__(self, n_continuous: int, category_sizes: Sequence[int],
                 width: int = LOCAL_WIDTH) -> None:
        super().__init__()
        self.n_continuous = int(n_continuous)
        self.category_sizes = tuple(int(x) for x in category_sizes)
        self.continuous_routes = nn.ModuleList(
            nn.Linear(1, width, bias=False) for _ in range(self.n_continuous)
        )
        self.continuous_types = nn.Parameter(torch.empty(self.n_continuous, width))
        self.continuous_gates = nn.Parameter(torch.zeros(self.n_continuous, width))
        self.category_embeddings = nn.ModuleList(
            nn.Embedding(size, width) for size in self.category_sizes
        )
        self.category_types = nn.Parameter(torch.empty(len(self.category_sizes), width))
        self.category_gates = nn.Parameter(torch.zeros(len(self.category_sizes), width))
        self.norm = nn.LayerNorm(width)
        nn.init.trunc_normal_(self.continuous_types, std=.02)
        nn.init.trunc_normal_(self.category_types, std=.02)

    def forward(self, continuous: Tensor, categorical: Tensor) -> Tensor:
        routes = [
            (layer(continuous[..., i:i + 1]) + self.continuous_types[i])
            * torch.sigmoid(self.continuous_gates[i])
            for i, layer in enumerate(self.continuous_routes)
        ]
        ids = categorical.to(dtype=torch.long)
        routes.extend(
            (embedding(ids[..., i]) + self.category_types[i])
            * torch.sigmoid(self.category_gates[i])
            for i, embedding in enumerate(self.category_embeddings)
        )
        return self.norm(torch.stack(routes, dim=0).sum(dim=0))


class _ExactInputEncoder(nn.Module):
    def __init__(self, n_event_continuous: int,
                 event_category_sizes: Sequence[int],
                 field_schema: Optional[EventFieldSchema]) -> None:
        super().__init__()
        self.n_event_continuous = int(n_event_continuous)
        self.event_category_sizes = tuple(int(x) for x in event_category_sizes)
        if field_schema is None:
            raise ValueError("an exact named EventFieldSchema is required")
        self.field_schema = field_schema
        if (len(self.field_schema.continuous_fields) != self.n_event_continuous or
                self.field_schema.category_sizes != self.event_category_sizes):
            raise ValueError("encoder dimensions do not match field_schema")

    def _validate(self, continuous: Tensor, categorical: Tensor,
                  receive_clock_ns: Tensor, cutoffs: Tensor,
                  decisions: Tensor) -> tuple[Tensor, Tensor, int]:
        return _validate_exact_inputs(continuous, categorical, receive_clock_ns,
                                      cutoffs, decisions, self.field_schema)


class LiTShortMemoryEncoder(_ExactInputEncoder):
    """Vectorized causal LiT-style last-64-event MBP-1 control."""

    def __init__(self, n_event_continuous: int,
                 event_category_sizes: Sequence[int] = (256, 256, 256, 256, 8), *,
                 bid_field_indices: Sequence[int] = (8, 10, 12),
                 ask_field_indices: Sequence[int] = (9, 11, 13),
                 field_schema: Optional[EventFieldSchema] = None) -> None:
        super().__init__(n_event_continuous, event_category_sizes, field_schema)
        bid = tuple(int(x) for x in bid_field_indices)
        ask = tuple(int(x) for x in ask_field_indices)
        if (not bid or not ask or any(x < 0 or x >= n_event_continuous for x in bid + ask)
                or set(bid) & set(ask)):
            raise ValueError("registered bid/ask field indices are invalid")
        self.register_buffer("bid_field_indices", torch.tensor(bid, dtype=torch.long),
                             persistent=True)
        self.register_buffer("ask_field_indices", torch.tensor(ask, dtype=torch.long),
                             persistent=True)
        cat_width = 16
        self.continuous_projection = nn.Linear(n_event_continuous, 384)
        self.category_embeddings = nn.ModuleList(
            nn.Embedding(size, cat_width) for size in self.event_category_sizes
        )
        self.general_projection = nn.Linear(
            384 + cat_width * len(self.event_category_sizes), MODEL_WIDTH
        )
        self.bid_projection = nn.Linear(len(bid), MODEL_WIDTH)
        self.ask_projection = nn.Linear(len(ask), MODEL_WIDTH)
        self.slot_type = nn.Parameter(torch.empty(3, MODEL_WIDTH))
        nn.init.trunc_normal_(self.slot_type, std=.02)
        self.patch_layers = nn.ModuleList(
            SDPAEncoderBlock(MODEL_WIDTH, 8, 2_048, causal=True, dropout=0.0)
            for _ in range(2)
        )
        self.lstm = nn.LSTM(MODEL_WIDTH, MODEL_WIDTH, num_layers=2,
                            batch_first=True)
        self.empty_memory = nn.Parameter(torch.empty(4, MODEL_WIDTH))
        nn.init.trunc_normal_(self.empty_memory, std=.02)
        self.last_complexity_receipt: Optional[EncoderComplexityReceipt] = None

    def gather_candidate_memory(self, continuous: Tensor, categorical: Tensor,
                                cutoffs: Tensor) -> Tensor:
        candidates = cutoffs.numel()
        if candidates == 0:
            return _activation_zeros(continuous, (0, 4, MODEL_WIDTH))
        offsets = torch.arange(64, device=continuous.device)[None]
        starts = (cutoffs - 64).clamp_min(0)
        lengths = cutoffs - starts
        indices = starts[:, None] + offsets
        valid = offsets < lengths[:, None]
        if continuous.shape[0]:
            source_x, source_k = continuous, categorical
        else:
            source_x = continuous.new_zeros((1, self.n_event_continuous))
            source_k = categorical.new_zeros(
                (1, len(self.event_category_sizes)), dtype=categorical.dtype
            )
        safe = indices.clamp(max=source_x.shape[0] - 1)
        x = source_x[safe] * valid[..., None].to(continuous.dtype)
        k = source_k[safe].to(dtype=torch.long)
        k = torch.where(valid[..., None], k, torch.zeros_like(k))
        cats = torch.cat([emb(k[..., i]) for i, emb in
                          enumerate(self.category_embeddings)], dim=-1)
        general = self.general_projection(torch.cat(
            (F.gelu(self.continuous_projection(x)), cats), dim=-1
        ))
        bid = self.bid_projection(x.index_select(-1, self.bid_field_indices))
        ask = self.ask_projection(x.index_select(-1, self.ask_field_indices))
        event_slots = torch.stack((general + self.slot_type[0],
                                   bid + self.slot_type[1],
                                   ask + self.slot_type[2]), dim=2)
        # Four consecutive events form one patch.  Slot identity is retained
        # before pooling; causal attention operates only across ordered patches.
        event_slots = event_slots.view(candidates, 16, 4, 3, MODEL_WIDTH)
        event_valid = valid.view(candidates, 16, 4)
        denom = event_valid.sum(dim=2).clamp_min(1).to(
            event_slots.dtype
        )[..., None, None]
        patches = (event_slots * event_valid[..., None, None].to(
            event_slots.dtype
        )).sum(dim=2)
        patches = (patches / denom).mean(dim=2)
        patch_valid = event_valid.any(dim=2)
        patches = patches + _sinusoidal_positions(
            16, MODEL_WIDTH, patches.device
        )[None].to(patches.dtype)
        patches = patches * patch_valid[..., None].to(patches.dtype)
        for layer in self.patch_layers:
            patches = layer(patches)
            patches = patches * patch_valid[..., None].to(patches.dtype)
        # CUDA/cuDNN may silently route LSTM through FP16 even inside a BF16
        # autocast region.  This control has only 16 recurrent steps, so run
        # that bounded segment in FP32 and never introduce FP16 range loss.
        with torch.autocast(device_type=patches.device.type, enabled=False):
            recurrent, _ = self.lstm(patches.float())
        output = self.empty_memory.to(recurrent.dtype)[None].expand(
            candidates, -1, -1
        ).clone()
        patch_lengths = (lengths + 3) // 4
        for row in range(candidates):
            count = int(patch_lengths[row])
            take = min(4, count)
            if take:
                output[row, -take:] = recurrent[row, count - take:count]
        self.last_complexity_receipt = EncoderComplexityReceipt(
            events_visible=int(cutoffs.max()), regular_blocks=0,
            candidates=candidates, recent_window_events=int(lengths.sum()),
            partial_block_events=0, band_60_blocks=0, band_300_blocks=0,
            band_900_blocks=0, regular_block_encodes=0,
            unique_prefixes=int(torch.unique(cutoffs).numel()),
            repeated_prefixes_reused=candidates - int(torch.unique(cutoffs).numel()),
        )
        return output

    def forward(self, event_continuous: Tensor, event_categorical: Tensor,
                candidate_cutoffs: Tensor, *, receive_clock_ns: Tensor,
                candidate_decision_ts_ns: Tensor, **_: object) -> Tensor:
        cutoffs, _, visible = self._validate(
            event_continuous, event_categorical, receive_clock_ns,
            candidate_cutoffs, candidate_decision_ts_ns
        )
        return self.gather_candidate_memory(event_continuous[:visible],
                                            event_categorical[:visible], cutoffs)


class CausalMultiresolutionEncoder(_ExactInputEncoder):
    """Cached custom M1 encoder with exact recent and receive-time memories."""

    def __init__(self, n_event_continuous: int,
                 event_category_sizes: Sequence[int] = (256, 256, 256, 256, 8), *,
                 field_schema: Optional[EventFieldSchema] = None) -> None:
        super().__init__(n_event_continuous, event_category_sizes, field_schema)
        self.block_size = 256
        self.stem = FieldPreservingStem(n_event_continuous, event_category_sizes,
                                        LOCAL_WIDTH)
        self.local_layers = nn.ModuleList(
            SDPAEncoderBlock(LOCAL_WIDTH, 4, 512, causal=True, dropout=0.0)
            for _ in range(2)
        )
        self.local_norm = nn.LayerNorm(LOCAL_WIDTH)
        self.local_pool = LearnedQueryPool(LOCAL_WIDTH, 4, 4)
        self.block_projection = nn.Linear(4 * LOCAL_WIDTH, 256)
        self.raw_projection = nn.Linear(4 * LOCAL_WIDTH, MODEL_WIDTH)
        self.gru_60 = nn.GRU(256, 256, batch_first=True)
        self.gru_300 = nn.GRU(256, 256, batch_first=True)
        self.gru_900 = nn.GRU(256, 256, batch_first=True)
        self.gru_full = nn.GRU(256, 256, batch_first=True)
        self.minute_projection = nn.Linear(256, MODEL_WIDTH)
        self.five_projection = nn.Linear(256, MODEL_WIDTH)
        self.long_projection = nn.Linear(512, MODEL_WIDTH)
        self.empty_memory = nn.Parameter(torch.empty(4, MODEL_WIDTH))
        nn.init.trunc_normal_(self.empty_memory, std=.02)
        self.last_complexity_receipt: Optional[EncoderComplexityReceipt] = None
        self._regular_encode_calls = 0

    def _encode_windows(self, continuous: Tensor, categorical: Tensor,
                        starts: Tensor, stops: Tensor) -> tuple[Tensor, Tensor]:
        batch = starts.numel()
        if batch == 0:
            return _activation_zeros(continuous, (0, 4, LOCAL_WIDTH)), torch.zeros(
                0, dtype=torch.long, device=continuous.device
            )
        lengths = stops - starts
        output = _activation_zeros(continuous, (batch, 4, LOCAL_WIDTH))
        nonempty = torch.nonzero(lengths > 0, as_tuple=False).flatten()
        if nonempty.numel() == 0:
            return output, lengths
        live_starts, live_lengths = starts[nonempty], lengths[nonempty]
        offsets = torch.arange(256, device=continuous.device)[None]
        indices = live_starts[:, None] + offsets
        valid = offsets < live_lengths[:, None]
        safe = indices.clamp(max=continuous.shape[0] - 1)
        x = continuous[safe] * valid[..., None].to(continuous.dtype)
        k = categorical[safe].to(dtype=torch.long)
        k = torch.where(valid[..., None], k, torch.zeros_like(k))
        h = self.stem(x, k)
        h = h + _sinusoidal_positions(256, LOCAL_WIDTH, h.device)[None].to(h.dtype)
        h = h * valid[..., None].to(h.dtype)
        for layer in self.local_layers:
            h = layer(h)
            h = h * valid[..., None].to(h.dtype)
        pooled = self.local_pool(self.local_norm(h), valid)
        output[nonempty] = pooled.to(output.dtype)
        return output, lengths

    def _encode_candidate_windows(
        self, continuous: Tensor, categorical: Tensor,
        starts: Tensor, stops: Tensor, *, chunk_size: int = 32,
    ) -> tuple[Tensor, Tensor]:
        """Encode candidate-local windows with bounded forward/backward memory."""
        if starts.shape != stops.shape or starts.ndim != 1:
            raise EntryModelRefusal("candidate window bounds must be aligned vectors")
        count = int(starts.numel())
        lengths = stops - starts
        if count == 0:
            return _activation_zeros(continuous, (0, 4, LOCAL_WIDTH)), lengths
        parts: list[Tensor] = []
        for chunk_start in range(0, count, chunk_size):
            chunk_stop = min(chunk_start + chunk_size, count)
            part_starts = starts[chunk_start:chunk_stop]
            part_stops = stops[chunk_start:chunk_stop]

            def encode(part_left: Tensor, part_right: Tensor) -> Tensor:
                pooled, _ = self._encode_windows(
                    continuous, categorical, part_left, part_right,
                )
                return pooled

            if self.training and torch.is_grad_enabled():
                pooled = checkpoint(
                    encode, part_starts, part_stops,
                    use_reentrant=False, preserve_rng_state=False,
                )
            else:
                pooled = encode(part_starts, part_stops)
            parts.append(pooled)
        self._candidate_window_chunks += (count + chunk_size - 1) // chunk_size
        self._candidate_window_chunk_high_water = max(
            self._candidate_window_chunk_high_water, min(count, chunk_size))
        return torch.cat(parts, dim=0), lengths

    def encode_session(self, event_continuous: Tensor, event_categorical: Tensor,
                       receive_clock_ns: Tensor, *, visible_events: int
                       ) -> M1SessionCache:
        visible = int(visible_events)
        if not 0 <= visible <= event_continuous.shape[0]:
            raise EntryModelRefusal("visible_events outside session")
        if (event_continuous.ndim != 2
                or event_continuous.shape[1] != self.n_event_continuous
                or event_categorical.shape != (
                    event_continuous.shape[0], len(self.event_category_sizes))
                or receive_clock_ns.dtype != torch.int64
                or receive_clock_ns.shape != (event_continuous.shape[0],)):
            raise EntryModelRefusal("session cache inputs do not match the bound schema")
        if not event_continuous.is_floating_point():
            raise EntryModelRefusal("session cache continuous values must be floating point")
        _integer("session cache categorical values", event_categorical)
        if event_continuous.device != event_categorical.device or (
                event_continuous.device != receive_clock_ns.device):
            raise EntryModelRefusal("session cache inputs must share one device")
        continuous = event_continuous[:visible]
        categorical = event_categorical[:visible]
        clocks = receive_clock_ns[:visible]
        if clocks.numel() > 1 and bool((clocks[1:] < clocks[:-1]).any()):
            raise EntryModelRefusal("visible session cache clocks decrease")
        if not bool(torch.isfinite(continuous).all()):
            raise EntryModelRefusal("visible session cache contains non-finite values")
        ids = categorical.to(dtype=torch.long)
        for field, size in enumerate(self.event_category_sizes):
            if ids.numel() and (int(ids[:, field].min()) < 0
                                or int(ids[:, field].max()) >= size):
                raise EntryModelRefusal("visible session cache category is out of range")
        blocks = visible // 256
        if blocks:
            starts = torch.arange(blocks, device=continuous.device) * 256
            stops = starts + 256
            summary_parts = []
            for chunk_start in range(0, blocks, 64):
                chunk_stop = min(chunk_start + 64, blocks)
                chunk_starts = starts[chunk_start:chunk_stop]
                chunk_stops = stops[chunk_start:chunk_stop]

                def encode_regular(part_starts: Tensor,
                                   part_stops: Tensor) -> Tensor:
                    pooled, _ = self._encode_windows(
                        continuous, categorical, part_starts, part_stops,
                    )
                    return self.block_projection(pooled.flatten(1))

                if self.training and torch.is_grad_enabled():
                    summary = checkpoint(
                        encode_regular, chunk_starts, chunk_stops,
                        use_reentrant=False, preserve_rng_state=False,
                    )
                else:
                    summary = encode_regular(chunk_starts, chunk_stops)
                summary_parts.append(summary)
            summaries = torch.cat(summary_parts, dim=0)
            ends = clocks[stops - 1]
            full, _ = self.gru_full(summaries[None])
            full_states = full[0]
            self._regular_encode_calls += 1
            self._regular_block_chunks = (blocks + 63) // 64
            self._regular_block_chunk_high_water = min(blocks, 64)
        else:
            summaries = _activation_zeros(continuous, (0, 256))
            ends = clocks.new_zeros((0,))
            full_states = _activation_zeros(continuous, (0, 256))
            self._regular_block_chunks = 0
            self._regular_block_chunk_high_water = 0
        return M1SessionCache(continuous, categorical, clocks, visible,
                              summaries, ends, full_states,
                              self.field_schema.sha256)

    @staticmethod
    def band_membership(cache: M1SessionCache, cutoff: int, decision_ts_ns: int,
                        seconds: int, *, include_partial: bool = True
                        ) -> tuple[int, ...]:
        full = int(cutoff) // 256
        clocks = cache.regular_end_clock_ns[:full]
        low = int(decision_ts_ns) - int(seconds) * 1_000_000_000
        left = int(torch.searchsorted(
            clocks, clocks.new_tensor(low), right=False
        ))
        right = int(torch.searchsorted(
            clocks, clocks.new_tensor(int(decision_ts_ns)), right=False
        ))
        selected = list(range(left, right))
        if include_partial and int(cutoff) % 256:
            partial_clock = int(cache.receive_clock_ns[int(cutoff) - 1])
            if low <= partial_clock < int(decision_ts_ns):
                selected.append(full)
        return tuple(int(x) for x in selected)

    @staticmethod
    def _run_masked_band(
        gru: nn.GRU, cache: M1SessionCache, cutoffs: Tensor, decisions: Tensor,
        partial_summaries: Tensor, has_partial: Tensor, seconds: int, *,
        chunk_size: int = 64,
    ) -> tuple[Tensor, int]:
        """Run one temporal band in bounded candidate chunks without host row loops."""
        candidates = int(cutoffs.numel())
        activation_dtype = partial_summaries.dtype
        result = torch.zeros((candidates, 256), device=cutoffs.device,
                             dtype=activation_dtype)
        blocks = int(cache.regular_summaries.shape[0])
        block_ids = torch.arange(blocks, device=cutoffs.device)
        total_work = 0
        for start in range(0, candidates, chunk_size):
            stop = min(start + chunk_size, candidates)
            chunk_cutoffs = cutoffs[start:stop]
            chunk_decisions = decisions[start:stop]
            full_counts = chunk_cutoffs // 256
            if blocks:
                clocks = cache.regular_end_clock_ns[None, :]
                low = chunk_decisions[:, None] - int(seconds) * 1_000_000_000
                regular_mask = (
                    (block_ids[None, :] < full_counts[:, None])
                    & (clocks >= low) & (clocks < chunk_decisions[:, None])
                )
                regular_lengths = regular_mask.sum(1, dtype=torch.long)
            else:
                regular_mask = torch.zeros(
                    (stop - start, 0), dtype=torch.bool, device=cutoffs.device
                )
                regular_lengths = torch.zeros(
                    stop - start, dtype=torch.long, device=cutoffs.device
                )
            local_partial = has_partial[start:stop]
            safe_last = (chunk_cutoffs - 1).clamp_min(0)
            partial_clocks = (
                cache.receive_clock_ns[safe_last]
                if cache.receive_clock_ns.numel() else
                torch.zeros_like(chunk_decisions)
            )
            partial_valid = (
                local_partial
                & (partial_clocks >= chunk_decisions - int(seconds) * 1_000_000_000)
                & (partial_clocks < chunk_decisions)
            )
            lengths = regular_lengths + partial_valid.to(torch.long)
            max_length = int(lengths.max()) if lengths.numel() else 0
            total_work += int(lengths.sum())
            if max_length == 0:
                continue
            dense = torch.zeros((stop - start, max_length, 256),
                                device=cutoffs.device, dtype=activation_dtype)
            if blocks and bool(regular_mask.any()):
                rows, source_blocks = torch.nonzero(regular_mask, as_tuple=True)
                destinations = regular_mask.cumsum(1)[rows, source_blocks] - 1
                dense[rows, destinations] = cache.regular_summaries[source_blocks]
            partial_rows = torch.nonzero(partial_valid, as_tuple=False).flatten()
            if partial_rows.numel():
                dense[partial_rows, regular_lengths[partial_rows]] = (
                    partial_summaries[start:stop][partial_rows]
                )
            active = torch.nonzero(lengths > 0, as_tuple=False).flatten()
            packed = pack_padded_sequence(
                dense[active], lengths[active].detach().cpu(), batch_first=True,
                enforce_sorted=False,
            )
            _, hidden = gru(packed)
            result[start + active] = hidden[0]
        return result, total_work

    def _validate_cache_queries(self, cache: M1SessionCache, cutoffs: Tensor,
                                decisions: Tensor) -> tuple[Tensor, Tensor]:
        if cache.schema_sha256 != self.field_schema.sha256:
            raise EntryModelRefusal("session cache field schema drifted")
        _integer("candidate_cutoffs", cutoffs)
        if decisions.dtype != torch.int64 or decisions.ndim != 1:
            raise EntryModelRefusal("candidate decision clocks must be exact int64")
        cutoffs = cutoffs.to(device=cache.receive_clock_ns.device, dtype=torch.long)
        decisions = decisions.to(device=cache.receive_clock_ns.device)
        if cutoffs.shape != decisions.shape or (cutoffs.numel() and (
                int(cutoffs.min()) < 0 or int(cutoffs.max()) > cache.visible_events)):
            raise EntryModelRefusal("candidate cache query is out of bounds")
        if decisions.numel() and (int(decisions.min()) < 0
                                  or int(decisions.max()) >= DEVELOPMENT_CUTOFF_NS):
            raise EntryModelRefusal("candidate cache query crosses the development wall")
        expected = torch.searchsorted(cache.receive_clock_ns, decisions, right=False)
        if not torch.equal(cutoffs, expected):
            raise EntryModelRefusal("candidate cache query cutoff is not lower_bound")
        return cutoffs, decisions

    def gather_candidate_memory(self, cache: M1SessionCache,
                                candidate_cutoffs: Tensor,
                                candidate_decision_ts_ns: Tensor) -> Tensor:
        cutoffs, candidate_decision_ts_ns = self._validate_cache_queries(
            cache, candidate_cutoffs, candidate_decision_ts_ns
        )
        candidates = cutoffs.numel()
        if candidates == 0:
            return _activation_zeros(cache.continuous, (0, 4, MODEL_WIDTH))
        self._candidate_window_chunks = 0
        self._candidate_window_chunk_high_water = 0
        starts = (cutoffs - 256).clamp_min(0)
        recent_pool, recent_lengths = self._encode_candidate_windows(
            cache.continuous, cache.categorical, starts, cutoffs
        )
        activation_dtype = recent_pool.dtype
        result = self.empty_memory.to(activation_dtype)[None].expand(
            candidates, -1, -1
        ).clone()
        nonempty = recent_lengths > 0
        if bool(nonempty.any()):
            result[nonempty, 0] = self.raw_projection(recent_pool[nonempty].flatten(1))
        remainders = cutoffs % 256
        partial_rows = torch.nonzero(remainders > 0, as_tuple=False).flatten()
        partial_summary_by_candidate = torch.zeros(
            (candidates, 256), device=cutoffs.device, dtype=activation_dtype
        )
        has_partial = remainders > 0
        partial_work = 0
        if partial_rows.numel():
            partial_starts = (cutoffs[partial_rows] // 256) * 256
            partial_stops = cutoffs[partial_rows]
            partial_pool, lengths = self._encode_candidate_windows(
                cache.continuous, cache.categorical, partial_starts, partial_stops
            )
            partial_summary = self.block_projection(partial_pool.flatten(1))
            partial_work = int(lengths.sum())
            partial_summary_by_candidate[partial_rows] = partial_summary
        full_states = torch.zeros((candidates, 256), device=cutoffs.device,
                                  dtype=activation_dtype)
        full_counts_all = cutoffs // 256
        complete_rows = torch.nonzero(
            (cutoffs > 0) & ~has_partial, as_tuple=False
        ).flatten()
        if complete_rows.numel():
            full_states[complete_rows] = cache.full_prefix_states[
                full_counts_all[complete_rows] - 1
            ]
        partial_state_rows = torch.nonzero(has_partial, as_tuple=False).flatten()
        if partial_state_rows.numel():
            rows = partial_state_rows
            full_counts = cutoffs[rows] // 256
            h0 = torch.zeros((1, rows.numel(), 256), device=cutoffs.device,
                             dtype=activation_dtype)
            prior = full_counts > 0
            if bool(prior.any()):
                h0[0, prior] = cache.full_prefix_states[full_counts[prior] - 1]
            _, hidden = self.gru_full(partial_summary_by_candidate[rows, None], h0)
            full_states[rows] = hidden[0]
        minute, w60 = self._run_masked_band(
            self.gru_60, cache, cutoffs, candidate_decision_ts_ns,
            partial_summary_by_candidate, has_partial, 60,
        )
        five, w300 = self._run_masked_band(
            self.gru_300, cache, cutoffs, candidate_decision_ts_ns,
            partial_summary_by_candidate, has_partial, 300,
        )
        fifteen, w900 = self._run_masked_band(
            self.gru_900, cache, cutoffs, candidate_decision_ts_ns,
            partial_summary_by_candidate, has_partial, 900,
        )
        result[:, 1] = self.minute_projection(minute)
        result[:, 2] = self.five_projection(five)
        result[:, 3] = self.long_projection(torch.cat((fifteen, full_states), dim=-1))
        self.last_complexity_receipt = EncoderComplexityReceipt(
            events_visible=cache.visible_events,
            regular_blocks=int(cache.regular_summaries.shape[0]),
            candidates=candidates, recent_window_events=int(recent_lengths.sum()),
            partial_block_events=partial_work, band_60_blocks=w60,
            band_300_blocks=w300, band_900_blocks=w900,
            regular_block_encodes=int(cache.regular_summaries.shape[0]),
            regular_block_chunks=int(self._regular_block_chunks),
            regular_block_chunk_high_water=int(
                self._regular_block_chunk_high_water),
            candidate_window_chunks=int(self._candidate_window_chunks),
            candidate_window_chunk_high_water=int(
                self._candidate_window_chunk_high_water),
            unique_prefixes=int(torch.unique(cutoffs).numel()),
            repeated_prefixes_reused=candidates - int(torch.unique(cutoffs).numel()),
        )
        return result

    def forward(self, event_continuous: Tensor, event_categorical: Tensor,
                candidate_cutoffs: Tensor, *, receive_clock_ns: Tensor,
                candidate_decision_ts_ns: Tensor, **_: object) -> Tensor:
        cutoffs, decisions, visible = self._validate(
            event_continuous, event_categorical, receive_clock_ns,
            candidate_cutoffs, candidate_decision_ts_ns
        )
        self._regular_encode_calls = 0
        cache = self.encode_session(event_continuous, event_categorical,
                                    receive_clock_ns, visible_events=visible)
        return self.gather_candidate_memory(cache, cutoffs, decisions)


class CurrentEncoderAdapter(_ExactInputEncoder):
    """Existing encoder adapter with the same exact-clock boundary proof."""

    def __init__(self, current: FullPrefixEntryModel,
                 field_schema: Optional[EventFieldSchema] = None) -> None:
        super().__init__(current.n_event_continuous, current.event_category_sizes,
                         field_schema)
        self.current = current

    def forward(self, event_continuous: Tensor, event_categorical: Tensor,
                candidate_cutoffs: Tensor, *, receive_clock_ns: Tensor,
                candidate_decision_ts_ns: Tensor, asset_idx: int | Tensor = 0,
                **_: object) -> Tensor:
        cutoffs, _, visible = self._validate(
            event_continuous, event_categorical, receive_clock_ns,
            candidate_cutoffs, candidate_decision_ts_ns
        )
        partition = partition_event_blocks(visible, cutoffs, self.current.block_size)
        if isinstance(asset_idx, Tensor):
            if asset_idx.ndim == 0:
                asset = int(asset_idx.item())
            elif asset_idx.shape == cutoffs.shape and asset_idx.numel():
                candidate_assets = asset_idx.to(
                    device=cutoffs.device, dtype=torch.long
                )
                first = candidate_assets[0]
                if not bool(torch.all(candidate_assets == first)):
                    raise EntryModelRefusal(
                        "CurrentEncoderAdapter requires one homogeneous session asset"
                    )
                asset = int(first.item())
            else:
                raise EntryModelRefusal(
                    "asset_idx must be scalar or candidate-aligned homogeneous"
                )
        else:
            asset = int(asset_idx)
        if not 0 <= asset < 3:
            raise EntryModelRefusal("asset_idx must identify one of three assets")
        state = self.current._prefix_states(event_continuous[:visible],
                                            event_categorical[:visible],
                                            partition, asset)
        return state[:, None].expand(-1, 4, -1)


class LosslessStaticTokenAdapter(nn.Module):
    def forward(self, values: Tensor) -> Tensor:
        if values.ndim != 2 or values.shape[1] != STATIC_FEATURES:
            raise EntryModelRefusal("static_features must be [candidates,1865]")
        if not values.is_floating_point() or not bool(torch.isfinite(values).all()):
            raise EntryModelRefusal("static_features must be finite floating point")
        return F.pad(values, (0, STATIC_PADDED - STATIC_FEATURES)).view(-1, 4, 512)

    def inverse(self, tokens: Tensor) -> Tensor:
        if tokens.ndim != 3 or tokens.shape[1:] != (4, 512):
            raise EntryModelRefusal("static tokens must be [candidates,4,512]")
        if not tokens.is_floating_point() or not bool(torch.isfinite(tokens).all()):
            raise EntryModelRefusal("static tokens must be finite floating point")
        flat = tokens.flatten(1)
        if not torch.equal(flat[:, STATIC_FEATURES:],
                           torch.zeros_like(flat[:, STATIC_FEATURES:])):
            raise EntryModelRefusal("static padding is not zero")
        return flat[:, :STATIC_FEATURES]


class CandidateCrossAttentionBlock(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.query_norm = nn.LayerNorm(512)
        self.memory_norm = nn.LayerNorm(512)
        self.attention = nn.MultiheadAttention(512, 8, dropout=0.0, batch_first=True)
        self.ff_norm = nn.LayerNorm(512)
        self.ff1 = nn.Linear(512, 2048)
        self.ff2 = nn.Linear(2048, 512)

    def forward(self, query: Tensor, memory: Tensor) -> Tensor:
        normalized = self.memory_norm(memory)
        update, _ = self.attention(self.query_norm(query), normalized, normalized,
                                   need_weights=False)
        query = query + update
        return query + self.ff2(F.gelu(self.ff1(self.ff_norm(query))))


@dataclass
class NeuralSufficiencyOutput:
    raw_memory: Tensor
    static_tokens: Optional[Tensor]
    context_token: Tensor
    decision_state: Tensor
    action_logit: Tensor
    ordinal_logits: Tensor
    value_distribution_logits: Tensor
    value_quantiles: Tensor
    expected_value: Tensor
    top3_logit: Tensor
    rank_score: Tensor
    mfe_quantiles: Tensor
    mae_quantiles: Tensor
    mfe: Tensor
    mae: Tensor
    wall_logit: Tensor
    time_to_peak: Tensor
    horizon_values: Tensor
    phase_logits: Tensor
    output_schema_sha256: str


def _ordered_quantiles(raw: Tensor) -> Tensor:
    return torch.cat((raw[:, :1], raw[:, :1] + torch.cumsum(
        F.softplus(raw[:, 1:]), dim=-1)), dim=-1)


def _nonnegative_ordered_quantiles(raw: Tensor) -> Tensor:
    first = F.softplus(raw[:, :1])
    return torch.cat((first, first + torch.cumsum(
        F.softplus(raw[:, 1:]), dim=-1)), dim=-1)


def _monotone_ordinal(raw: Tensor) -> Tensor:
    return torch.cat((raw[:, :1], raw[:, :1] - torch.cumsum(
        F.softplus(raw[:, 1:]), dim=-1)), dim=-1)


class SharedCandidateDecisionHead(nn.Module):
    """Strictly shareable candidate/context/raw/static cross-attention head."""

    def __init__(self, n_candidate_features: int, n_context_continuous: int,
                 n_context_types: int, *, n_value_bins: int = 5,
                 n_phases: int = 8, horizons: Sequence[int] = DEFAULT_HORIZONS,
                 max_context_history: int = 64) -> None:
        super().__init__()
        if tuple(int(x) for x in horizons) != DEFAULT_HORIZONS:
            raise ValueError(f"horizons are frozen at {DEFAULT_HORIZONS}")
        if int(n_candidate_features) <= 0 or int(n_value_bins) <= 1:
            raise ValueError("candidate feature and value-bin dimensions are invalid")
        if int(n_phases) != 8:
            raise ValueError("the phase head is frozen at eight phases")
        self.n_candidate_features = int(n_candidate_features)
        self.n_value_bins = int(n_value_bins)
        self.n_phases = int(n_phases)
        self.horizons = DEFAULT_HORIZONS
        self.query = nn.Parameter(torch.empty(512)); nn.init.trunc_normal_(self.query, std=.02)
        self.asset_embedding = nn.Embedding(3, 512)
        self.candidate_norm = nn.LayerNorm(n_candidate_features)
        self.candidate_projection = nn.Linear(n_candidate_features, 512)
        self.context_encoder = TypedContextEncoder(
            n_context_continuous, n_context_types,
            max_history=max_context_history, dropout=0.0
        )
        self.context_projection = nn.Linear(128, 512)
        self.static_adapter = LosslessStaticTokenAdapter()
        self.raw_slot_embedding = nn.Parameter(torch.empty(4, 512))
        self.context_slot_embedding = nn.Parameter(torch.empty(1, 512))
        self.static_slot_embedding = nn.Parameter(torch.empty(4, 512))
        for value in (self.raw_slot_embedding, self.context_slot_embedding,
                      self.static_slot_embedding):
            nn.init.trunc_normal_(value, std=.02)
        self.cross_attention = nn.ModuleList(CandidateCrossAttentionBlock()
                                             for _ in range(2))
        self.asset_adapters = nn.ModuleList(AssetAdapter() for _ in range(3))
        self.final_norm = nn.LayerNorm(512)
        self.action_head = nn.Linear(512, 1)
        self.ordinal_head = nn.Linear(512, 4)
        self.value_distribution_head = nn.Linear(512, n_value_bins)
        self.value_quantile_head = nn.Linear(512, 3)
        self.expected_value_head = nn.Linear(512, 1)
        self.top3_head = nn.Linear(512, 1)
        self.rank_head = nn.Linear(512, 1)
        self.mfe_quantile_head = nn.Linear(512, 3)
        self.mae_quantile_head = nn.Linear(512, 3)
        self.wall_head = nn.Linear(512, 1)
        self.time_to_peak_head = nn.Linear(512, 1)
        self.horizon_head = nn.Linear(512, 6)
        self.phase_head = nn.Linear(512, n_phases)
        self.output_schema_sha256 = self._schema_hash()

    def _schema_hash(self) -> str:
        schema = {
            "action_logit": ["C"], "decision_state": ["C", 512],
            "expected_value": ["C"],
            "horizon_seconds": list(self.horizons), "horizon_values": ["C", 6],
            "mae": ["C", "nonnegative"],
            "mae_quantiles": ["C", 3, "nonnegative_nondecreasing"],
            "mfe": ["C", "nonnegative"],
            "mfe_quantiles": ["C", 3, "nonnegative_nondecreasing"],
            "ordinal_logits": ["C", 4, "nonincreasing"],
            "phase_logits": ["C", self.n_phases], "raw_memory": ["C", 4, 512],
            "rank_score": ["C"],
            "static_tokens": ["C", 4, 512, "optional_lossless"],
            "time_to_peak": ["C"], "top3_logit": ["C"],
            "value_distribution_logits": ["C", self.n_value_bins],
            "value_quantiles": ["C", 3],
            "wall_logit": ["C"],
        }
        return hashlib.sha256(json.dumps(schema, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _assets(asset_idx: int | Tensor, count: int, device: torch.device) -> Tensor:
        if isinstance(asset_idx, int):
            result = torch.full((count,), asset_idx, device=device, dtype=torch.long)
        else:
            result = asset_idx.to(device=device, dtype=torch.long)
            if result.ndim == 0:
                result = result.expand(count)
        if result.shape != (count,) or (count and
                (int(result.min()) < 0 or int(result.max()) >= 3)):
            raise EntryModelRefusal("asset_idx must identify one of three assets")
        return result

    def decorated_memory(self, raw_memory: Tensor, context_token: Tensor,
                         static_tokens: Optional[Tensor]) -> Tensor:
        pieces = (raw_memory + self.raw_slot_embedding[None],
                  context_token + self.context_slot_embedding[None])
        if static_tokens is not None:
            pieces += (static_tokens + self.static_slot_embedding[None],)
        return torch.cat(pieces, dim=1)

    def forward(self, raw_memory: Tensor, candidate_features: Tensor,
                context_values: Tensor, context_type_ids: Tensor,
                context_valid: Tensor, asset_idx: int | Tensor, *,
                static_features: Optional[Tensor] = None) -> NeuralSufficiencyOutput:
        if raw_memory.ndim != 3 or raw_memory.shape[1:] != (4, 512):
            raise EntryModelRefusal("raw_memory must be [candidates,4,512]")
        count = raw_memory.shape[0]
        if candidate_features.shape != (count, self.n_candidate_features):
            raise EntryModelRefusal("candidate_features has wrong shape")
        if (not raw_memory.is_floating_point()
                or not bool(torch.isfinite(raw_memory).all())
                or not candidate_features.is_floating_point()
                or not bool(torch.isfinite(candidate_features).all())):
            raise EntryModelRefusal("raw memory and candidate features must be finite")
        assets = self._assets(asset_idx, count, raw_memory.device)
        context_token = self.context_projection(self.context_encoder(
            context_values, context_type_ids, context_valid
        ))[:, None]
        static_tokens = (None if static_features is None
                         else self.static_adapter(static_features))
        memory = self.decorated_memory(raw_memory, context_token, static_tokens)
        query = (self.query[None] + self.asset_embedding(assets)
                 + self.candidate_projection(self.candidate_norm(candidate_features)))[:, None]
        for block in self.cross_attention:
            query = block(query, memory)
        state = query[:, 0]
        adapted = torch.empty_like(state)
        for asset, adapter in enumerate(self.asset_adapters):
            selected = assets == asset
            if bool(selected.any()):
                adapted[selected] = adapter(state[selected])
        state = self.final_norm(adapted)
        scalar = lambda head: head(state).squeeze(-1)
        value_q = _ordered_quantiles(self.value_quantile_head(state))
        mfe_q = _nonnegative_ordered_quantiles(self.mfe_quantile_head(state))
        mae_q = _nonnegative_ordered_quantiles(self.mae_quantile_head(state))
        return NeuralSufficiencyOutput(
            raw_memory, static_tokens, context_token, state,
            scalar(self.action_head), _monotone_ordinal(self.ordinal_head(state)),
            self.value_distribution_head(state), value_q,
            scalar(self.expected_value_head), scalar(self.top3_head),
            scalar(self.rank_head), mfe_q, mae_q, mfe_q[:, 1], mae_q[:, 1],
            scalar(self.wall_head), scalar(self.time_to_peak_head),
            self.horizon_head(state), self.phase_head(state),
            self.output_schema_sha256,
        )


class NeuralSufficiencyModel(nn.Module):
    def __init__(self, encoder: nn.Module, head: SharedCandidateDecisionHead) -> None:
        super().__init__()
        self.encoder = encoder
        self.head = head
        self.shared_head_initial_bytes = module_state_bytes(head)

    def forward(self, *, event_continuous: Tensor, event_categorical: Tensor,
                receive_clock_ns: Tensor, candidate_cutoffs: Tensor,
                candidate_decision_ts_ns: Tensor, candidate_features: Tensor,
                context_values: Tensor, context_type_ids: Tensor,
                context_valid: Tensor, asset_idx: int | Tensor,
                static_features: Optional[Tensor] = None) -> NeuralSufficiencyOutput:
        raw = self.encoder(event_continuous, event_categorical, candidate_cutoffs,
                           receive_clock_ns=receive_clock_ns,
                           candidate_decision_ts_ns=candidate_decision_ts_ns,
                           asset_idx=asset_idx)
        return self.head(raw, candidate_features, context_values, context_type_ids,
                         context_valid, asset_idx, static_features=static_features)


def module_state_bytes(module: nn.Module) -> bytes:
    chunks: list[bytes] = []
    for name, value in sorted(module.state_dict().items()):
        cpu = value.detach().cpu().contiguous()
        chunks.extend((name.encode(), b"\0", str(cpu.dtype).encode(), b"\0",
                       repr(tuple(cpu.shape)).encode(), b"\0",
                       cpu.numpy().tobytes(), b"\0"))
    return b"".join(chunks)


def shared_head_sha256(module: nn.Module) -> str:
    return hashlib.sha256(module_state_bytes(module)).hexdigest()


def build_shared_arms(encoders: Mapping[str, nn.Module],
                      shared_head: SharedCandidateDecisionHead, *,
                      require_canonical: bool = False
                      ) -> dict[str, NeuralSufficiencyModel]:
    if require_canonical:
        if tuple(encoders) != CANONICAL_ARMS:
            raise EntryModelRefusal(f"canonical arm order must be {CANONICAL_ARMS}")
        types = {"C0": CurrentEncoderAdapter, "C1": CurrentEncoderAdapter,
                 "L0": LiTShortMemoryEncoder, "L1": LiTShortMemoryEncoder,
                 "M1": CausalMultiresolutionEncoder}
        for name, expected in types.items():
            if not isinstance(encoders[name], expected):
                raise EntryModelRefusal(f"{name} must be {expected.__name__}")
    arms = {name: NeuralSufficiencyModel(encoder, copy.deepcopy(shared_head))
            for name, encoder in encoders.items()}
    expected = module_state_bytes(shared_head)
    if any(arm.shared_head_initial_bytes != expected for arm in arms.values()):
        raise RuntimeError("shared-head strict initialization failed")
    pointers = [{p.data_ptr() for p in arm.head.parameters()} for arm in arms.values()]
    if any(left & right for i, left in enumerate(pointers)
           for right in pointers[i + 1:]):
        raise RuntimeError("shared heads alias parameter storage")
    encoder_pointers = [
        {p.data_ptr() for p in arm.encoder.parameters()} for arm in arms.values()
    ]
    if any(left & right for i, left in enumerate(encoder_pointers)
           for right in encoder_pointers[i + 1:]):
        raise RuntimeError("encoder arms alias parameter storage")
    return arms


def build_five_arm_registry(c0: nn.Module, c1: nn.Module, lit: nn.Module,
                            m1: nn.Module, shared_head: SharedCandidateDecisionHead
                            ) -> dict[str, NeuralSufficiencyModel]:
    return build_shared_arms({"C0": copy.deepcopy(c0), "C1": copy.deepcopy(c1),
                              "L0": copy.deepcopy(lit), "L1": copy.deepcopy(lit),
                              "M1": copy.deepcopy(m1)},
                             shared_head, require_canonical=True)


def assert_lit_checkpoint_identity(arms: Mapping[str, NeuralSufficiencyModel]) -> str:
    if "L0" not in arms or "L1" not in arms:
        raise EntryModelRefusal("L0 and L1 are required")
    left, right = module_state_bytes(arms["L0"].encoder), module_state_bytes(arms["L1"].encoder)
    if left != right:
        raise EntryModelRefusal("L0/L1 encoder checkpoints differ")
    if any(a.data_ptr() == b.data_ptr() for a, b in
           zip(arms["L0"].encoder.parameters(), arms["L1"].encoder.parameters())):
        raise EntryModelRefusal("L0/L1 encoder checkpoint storage aliases")
    return hashlib.sha256(left).hexdigest()


@dataclass(frozen=True)
class FieldRoutingReceipt:
    continuous_mutations: tuple[bool, ...]
    categorical_mutations: tuple[bool, ...]
    continuous_gradients: tuple[bool, ...]
    embedding_gradients: tuple[bool, ...]

    @property
    def passed(self) -> bool:
        return all(self.continuous_mutations + self.categorical_mutations
                   + self.continuous_gradients + self.embedding_gradients)


def field_routing_competence(encoder: nn.Module, *, event_continuous: Tensor,
                             event_categorical: Tensor, receive_clock_ns: Tensor,
                             candidate_cutoffs: Tensor,
                             candidate_decision_ts_ns: Tensor,
                             mutation_row: int = 0) -> FieldRoutingReceipt:
    """Reusable synthetic mutation/gradient gate for every input route."""
    encoder.zero_grad(set_to_none=True)
    values = event_continuous.detach().clone().requires_grad_(True)
    base = encoder(values, event_categorical, candidate_cutoffs,
                   receive_clock_ns=receive_clock_ns,
                   candidate_decision_ts_ns=candidate_decision_ts_ns)
    base.sum().backward()
    continuous_gradients = tuple(bool(values.grad[:, i].abs().sum() > 0)
                                 for i in range(values.shape[1]))
    if isinstance(encoder, CurrentEncoderAdapter):
        embeddings = encoder.current.local.category_embeddings
    elif hasattr(encoder, "stem"):
        embeddings = encoder.stem.category_embeddings
    elif hasattr(encoder, "category_embeddings"):
        embeddings = encoder.category_embeddings
    else:
        raise EntryModelRefusal(
            "field routing cannot resolve categorical embedding routes"
        )
    embedding_gradients = tuple(e.weight.grad is not None and
                                bool(e.weight.grad.abs().sum() > 0) for e in embeddings)
    continuous_mutations, categorical_mutations = [], []
    with torch.no_grad():
        reference = base.detach()
        for field in range(event_continuous.shape[1]):
            mutant = event_continuous.clone(); mutant[mutation_row, field] += 1.25
            changed = encoder(mutant, event_categorical, candidate_cutoffs,
                receive_clock_ns=receive_clock_ns,
                candidate_decision_ts_ns=candidate_decision_ts_ns)
            continuous_mutations.append(bool((changed - reference).abs().max() > 1e-6))
        for field, size in enumerate(encoder.event_category_sizes):
            mutant = event_categorical.clone()
            mutant[mutation_row, field] = (mutant[mutation_row, field] + 1) % size
            changed = encoder(event_continuous, mutant, candidate_cutoffs,
                receive_clock_ns=receive_clock_ns,
                candidate_decision_ts_ns=candidate_decision_ts_ns)
            categorical_mutations.append(bool((changed - reference).abs().max() > 1e-6))
    receipt = FieldRoutingReceipt(tuple(continuous_mutations),
        tuple(categorical_mutations), continuous_gradients, embedding_gradients)
    if not receipt.passed:
        raise EntryModelRefusal("field routing competence failed")
    return receipt


class LastRowReconstructionProbe(nn.Module):
    def __init__(self, n_continuous: int, category_sizes: Sequence[int]) -> None:
        super().__init__()
        self.trunk = nn.Sequential(nn.Flatten(), nn.Linear(2048, 512), nn.GELU())
        self.continuous = nn.Linear(512, n_continuous)
        self.categories = nn.ModuleList(nn.Linear(512, int(size))
                                        for size in category_sizes)

    def forward(self, memory: Tensor) -> tuple[Tensor, tuple[Tensor, ...]]:
        state = self.trunk(memory)
        return self.continuous(state), tuple(head(state) for head in self.categories)


@dataclass(frozen=True)
class ReconstructionReceipt:
    continuous_mae: float
    categorical_accuracy: float
    passed: bool


def reconstruction_receipt(probe: LastRowReconstructionProbe, memory: Tensor,
                           continuous: Tensor, categorical: Tensor
                           ) -> ReconstructionReceipt:
    predicted, logits = probe(memory)
    mae = float((predicted - continuous).abs().mean().detach())
    correct = torch.stack([value.argmax(-1) == categorical[:, i]
                           for i, value in enumerate(logits)], dim=1)
    accuracy = float(correct.float().mean().detach())
    return ReconstructionReceipt(mae, accuracy, mae <= 1e-3 and accuracy == 1.0)


def assert_tensor_tree_identical(left: object, right: object) -> None:
    if isinstance(left, Tensor) and isinstance(right, Tensor):
        if not torch.equal(left, right):
            raise EntryModelRefusal("suffix changed a tensor output")
    elif hasattr(left, "__dataclass_fields__") and type(left) is type(right):
        for name in left.__dataclass_fields__:  # type: ignore[attr-defined]
            assert_tensor_tree_identical(getattr(left, name), getattr(right, name))
    elif left != right:
        raise EntryModelRefusal("suffix changed an output")


@dataclass(frozen=True)
class StageTrainingSpec:
    name: str
    max_epochs: int
    patience: int
    minimum_relative_improvement: float = .001


STAGE_SPECS = MappingProxyType({
    "field_survival": StageTrainingSpec("field_survival", 8, 2),
    "pointwise_dense": StageTrainingSpec("pointwise_dense", 12, 3),
    "grouped_atlas": StageTrainingSpec("grouped_atlas", 6, 2),
})


@dataclass(frozen=True)
class EpochTrainingReceipt:
    epoch: int
    train_loss: float
    validation_loss: float
    gradient_norm: float
    parameter_delta: float


@dataclass(frozen=True)
class StageTrainingReceipt:
    spec: StageTrainingSpec
    epochs: tuple[EpochTrainingReceipt, ...]
    best_epoch: int
    best_validation_loss: float
    best_state_sha256: str
    best_reloaded: bool
    row_manifest_sha256: str
    first_day: int
    last_day: int


@dataclass(frozen=True)
class FrozenRowManifest:
    candidate_id: tuple[str, ...]
    asset: tuple[str, ...]
    day: tuple[int, ...]
    split: tuple[str, ...]
    chronology: str
    receipt_sha256: str

    @classmethod
    def build(cls, candidate_id: Sequence[str], asset: Sequence[str],
              day: Sequence[int], *, chronology: str) -> "FrozenRowManifest":
        ids, assets, days = tuple(map(str, candidate_id)), tuple(map(str, asset)), tuple(map(int, day))
        if not ids or len(ids) != len(assets) or len(ids) != len(days) or len(set(ids)) != len(ids):
            raise EntryModelRefusal("training row manifest is empty, misaligned, or duplicated")
        split = tuple(frozen_chronology_split(np.asarray(days, dtype=np.int64),
                                              chronology).tolist())
        payload = {"candidate_id": ids, "asset": assets, "day": days,
                   "split": split, "chronology": chronology.upper()}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        return cls(ids, assets, days, split, chronology.upper(), digest)

    @classmethod
    def build_fit_validation(cls, candidate_id: Sequence[str], asset: Sequence[str],
                             day: Sequence[int], *, chronology: str
                             ) -> "FrozenRowManifest":
        """Final chronological 10% of fit days is validation for E4--E8."""
        ids, assets, days = tuple(map(str, candidate_id)), tuple(map(str, asset)), tuple(map(int, day))
        if not ids or len(ids) != len(assets) or len(ids) != len(days) or len(set(ids)) != len(ids):
            raise EntryModelRefusal("training row manifest is empty, misaligned, or duplicated")
        unique = sorted(set(days)); n_validation = max(1, int(np.ceil(.10 * len(unique))))
        if len(unique) < 2:
            raise EntryModelRefusal("chronological fit/validation needs at least two fit days")
        validation = set(unique[-n_validation:])
        split = tuple("VALIDATION" if value in validation else "TRAIN" for value in days)
        if "TRAIN" not in split or "VALIDATION" not in split:
            raise EntryModelRefusal("fit/validation chronology is degenerate")
        payload = {"candidate_id": ids, "asset": assets, "day": days,
                   "split": split, "chronology": str(chronology).upper()}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
        return cls(ids, assets, days, split, str(chronology).upper(), digest)


def train_chronological_stage(model: nn.Module, optimizer: torch.optim.Optimizer, *,
                              stage: str,
                              row_manifest: FrozenRowManifest,
                              train_epoch: Callable[[nn.Module, torch.optim.Optimizer,
                                                     FrozenRowManifest], Tensor],
                              validate_epoch: Callable[[nn.Module, FrozenRowManifest], Tensor]
                              ) -> StageTrainingReceipt:
    """Frozen 8/12/6 best-checkpoint law; callbacks own chronological fit data."""
    if stage not in STAGE_SPECS:
        raise EntryModelRefusal(f"unknown training stage {stage}")
    spec = STAGE_SPECS[stage]
    best, best_epoch, best_state, stale, qualifying_improvements = float("inf"), -1, None, 0, 0
    history = []
    previous = {name: p.detach().clone() for name, p in model.named_parameters()}
    for epoch in range(spec.max_epochs):
        loss = train_epoch(model, optimizer, row_manifest)
        grad = sum(float(p.grad.norm()) for p in model.parameters() if p.grad is not None)
        delta = sum(float((p.detach() - previous[name]).norm())
                    for name, p in model.named_parameters())
        previous = {name: p.detach().clone() for name, p in model.named_parameters()}
        validation_tensor = validate_epoch(model, row_manifest)
        validation = float(validation_tensor.detach())
        train_value = float(loss.detach())
        if (loss.ndim != 0 or validation_tensor.ndim != 0
                or not np.isfinite(train_value) or not np.isfinite(validation)
                or not np.isfinite(grad) or grad <= 0
                or not np.isfinite(delta) or delta <= 0):
            raise EntryModelRefusal(
                f"{stage} epoch {epoch} has nonfinite/zero optimization evidence"
            )
        history.append(EpochTrainingReceipt(epoch, train_value, validation,
                                            grad, delta))
        if best_state is None or validation < best * (1 - spec.minimum_relative_improvement):
            if best_state is not None:
                qualifying_improvements += 1
            best, best_epoch, best_state, stale = validation, epoch, copy.deepcopy(model.state_dict()), 0
        else:
            stale += 1
        if epoch >= 1 and stale >= spec.patience:
            break
    if (best_state is None or len(history) < 2 or qualifying_improvements < 1):
        raise EntryModelRefusal(
            f"{stage} did not demonstrate a post-initial 0.1% validation improvement"
        )
    model.load_state_dict(best_state, strict=True)
    reloaded_hash = hashlib.sha256(module_state_bytes(model)).hexdigest()
    expected_chunks: list[bytes] = []
    for name, value in sorted(best_state.items()):
        cpu = value.detach().cpu().contiguous()
        expected_chunks.extend((name.encode(), b"\0", str(cpu.dtype).encode(), b"\0",
                                repr(tuple(cpu.shape)).encode(), b"\0",
                                cpu.numpy().tobytes(), b"\0"))
    expected_hash = hashlib.sha256(b"".join(expected_chunks)).hexdigest()
    if reloaded_hash != expected_hash:
        raise EntryModelRefusal(f"{stage} best-checkpoint reload hash differs")
    return StageTrainingReceipt(spec, tuple(history), best_epoch, best,
        reloaded_hash, True,
        row_manifest.receipt_sha256, min(row_manifest.day), max(row_manifest.day))


def validate_balanced_overfit_inputs(asset_idx: Tensor, target: Tensor
                                     ) -> tuple[tuple[int, ...], tuple[int, ...]]:
    positive = tuple(int(((asset_idx == asset) & (target == 1)).sum()) for asset in range(3))
    negative = tuple(int(((asset_idx == asset) & (target == 0)).sum()) for asset in range(3))
    if min(positive + negative) < 32:
        raise EntryModelRefusal("balanced competence needs >=32 positives/negatives per asset")
    return positive, negative


__all__ = [
    "CANONICAL_ARMS", "CausalMultiresolutionEncoder", "CurrentEncoderAdapter",
    "EncoderComplexityReceipt", "EventFieldSchema", "FieldPreservingStem",
    "LiTShortMemoryEncoder", "LosslessStaticTokenAdapter", "M1SessionCache",
    "NeuralSufficiencyModel", "NeuralSufficiencyOutput",
    "SharedCandidateDecisionHead", "assert_lit_checkpoint_identity",
    "EpochTrainingReceipt", "FieldRoutingReceipt", "FrozenRowManifest",
    "LastRowReconstructionProbe",
    "ReconstructionReceipt", "STAGE_SPECS", "StageTrainingReceipt",
    "StageTrainingSpec", "assert_tensor_tree_identical",
    "build_five_arm_registry", "build_shared_arms", "generic_event_schema",
    "field_routing_competence", "module_state_bytes", "reconstruction_receipt",
    "shared_head_sha256", "train_chronological_stage",
    "validate_balanced_overfit_inputs",
]
