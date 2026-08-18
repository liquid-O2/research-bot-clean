"""Fixed-capacity shallow learner and action binding for the label atlas."""
from __future__ import annotations

from dataclasses import dataclass, replace
import copy
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
import torch
from torch import nn

from .causal_label_atlas import ProbeSpec, ProbeTarget, PADDED_OUTPUT_WIDTH
from .atlas_losses import loss_for_probe


STATIC_WIDTH = 1865
STAGE_PRETEXT_WIDTH = 512
PRETEXT_WIDTH = 2 * STAGE_PRETEXT_WIDTH
INPUT_WIDTH = STATIC_WIDTH + PRETEXT_WIDTH
UNIVERSAL_OUTPUT_WIDTH = PADDED_OUTPUT_WIDTH
_STAGE_FIT_DAY_BOUNDS = {
    "E1": ("2021-05-31", "2021-09-30"),
    "E2": ("2021-05-31", "2022-03-11"),
    "E1R": ("2021-05-31", "2021-07-09"),
    "E2R": ("2021-05-31", "2021-08-13"),
}
_DEVELOPMENT_LAST_DAY = "2025-06-30"
_DEFAULT_STREAM_EVENTS = 4096


class AtlasProbeRefusal(RuntimeError):
    pass


def _frozen_stage_indices(days: Sequence[object], stage_id: str) -> np.ndarray:
    if stage_id not in _STAGE_FIT_DAY_BOUNDS:
        raise AtlasProbeRefusal("unknown frozen atlas chronology stage")
    raw = np.asarray(days).astype(str)
    if raw.ndim != 1:
        raise AtlasProbeRefusal("candidate days must be one-dimensional")
    value = np.asarray([f"{day[:4]}-{day[4:6]}-{day[6:]}" if len(day) == 8
                        and day.isdigit() else day for day in raw])
    if any(len(day) != 10 or day[4] != "-" or day[7] != "-"
           or not day.replace("-", "").isdigit() for day in value):
        raise AtlasProbeRefusal("candidate days must be canonical YYYY-MM-DD")
    lower, upper = _STAGE_FIT_DAY_BOUNDS[stage_id]
    return np.flatnonzero((value >= lower) & (value <= upper)).astype(np.int64)


def _require_frozen_indices(days: Sequence[object], stage_id: str,
                            supplied: Sequence[int]) -> np.ndarray:
    expected = _frozen_stage_indices(days, stage_id)
    actual = np.asarray(supplied, np.int64)
    if actual.ndim != 1 or len(np.unique(actual)) != len(actual) \
            or set(actual.tolist()) != set(expected.tolist()):
        raise AtlasProbeRefusal("fit rows differ from frozen candidate-day chronology")
    return expected


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _array_bytes(value: np.ndarray) -> bytes:
    a = np.ascontiguousarray(value)
    return (str(a.dtype).encode() + b"|" + json.dumps(a.shape).encode() + b"|" + a.tobytes())


def _torch_device(device: str | torch.device | None) -> torch.device:
    resolved = torch.device("cpu" if device is None else device)
    if resolved.type not in {"cpu", "cuda"}:
        raise AtlasProbeRefusal("atlas learner device must be cpu or cuda")
    if resolved.type == "cuda" and not torch.cuda.is_available():
        raise AtlasProbeRefusal("requested CUDA atlas learner device is unavailable")
    torch.use_deterministic_algorithms(True)
    if resolved.type == "cuda":
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    return resolved


def _chunk_size(value: int) -> int:
    size = int(value)
    if size < 1:
        raise AtlasProbeRefusal("stream chunk size must be positive")
    return size


def _frozen_array(value: Any, dtype: Any | None = None) -> np.ndarray:
    result = np.ascontiguousarray(value, dtype=dtype)
    result.setflags(write=False)
    return result


def _model_state_sha256(model: nn.Module) -> str:
    return _sha(b"".join(
        name.encode() + b"\0" + _array_bytes(tensor.detach().cpu().numpy()) + b"\0"
        for name, tensor in sorted(model.state_dict().items())
    ))


@dataclass(frozen=True)
class FitOnlyNormalizer:
    location: np.ndarray
    scale: np.ndarray
    constant_zero_mask: np.ndarray
    constant_zero_sha256: str
    receipt_sha256: str

    @classmethod
    def fit(cls, x_fit: np.ndarray) -> "FitOnlyNormalizer":
        x = np.asarray(x_fit, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != INPUT_WIDTH or not len(x) or not np.all(np.isfinite(x)):
            raise AtlasProbeRefusal("normalizer fit input must be finite and have width 2377")
        location = x.mean(axis=0, dtype=np.float64)
        scale = x.std(axis=0, dtype=np.float64)
        constant = scale == 0
        scale[constant] = 1.0
        for a in (location, scale, constant):
            a.setflags(write=False)
        constant_hash = _sha(_array_bytes(constant))
        receipt = _sha(_array_bytes(location) + _array_bytes(scale) + _array_bytes(constant))
        return cls(location, scale, constant, constant_hash, receipt)

    def transform(self, x: np.ndarray) -> np.ndarray:
        value = np.asarray(x, dtype=np.float64)
        if value.ndim != 2 or value.shape[1] != INPUT_WIDTH or not np.all(np.isfinite(value)):
            raise AtlasProbeRefusal("normalizer transform input must be finite and have width 2377")
        result = (value - self.location) / self.scale
        result[:, self.constant_zero_mask] = 0.0
        if not np.all(np.isfinite(result)):
            raise AtlasProbeRefusal("normalized probe input is non-finite")
        return result.astype(np.float32)


class AtlasProbeNet(nn.Module):
    """Universal probe architecture; target semantics never alter parameters."""
    def __init__(self) -> None:
        super().__init__()
        self.layer_norm = nn.LayerNorm(INPUT_WIDTH)
        self.linear_256 = nn.Linear(INPUT_WIDTH, 256)
        self.linear_128 = nn.Linear(256, 128)
        self.head = nn.Linear(128, UNIVERSAL_OUTPUT_WIDTH)
        self.activation = nn.GELU()

    def latent(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 2 or x.shape[1] != INPUT_WIDTH or not bool(torch.isfinite(x).all()):
            raise AtlasProbeRefusal("probe input must be finite and have width 2377")
        return self.linear_128(self.activation(self.linear_256(self.layer_norm(x))))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.latent(x))

    @property
    def parameter_count(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def canonical_state_bytes(self) -> bytes:
        chunks: list[bytes] = []
        for name, tensor in sorted(self.state_dict().items()):
            value = tensor.detach().cpu().numpy()
            chunks.extend((name.encode(), b"\0", _array_bytes(value), b"\0"))
        return b"".join(chunks)

    @property
    def canonical_state_sha256(self) -> str:
        return _sha(self.canonical_state_bytes())

    def strict_load_initialization(self, source: "AtlasProbeNet") -> None:
        self.load_state_dict(copy.deepcopy(source.state_dict()), strict=True)
        if self.canonical_state_sha256 != source.canonical_state_sha256:
            raise AtlasProbeRefusal("strict initialization reload differs")

    def frozen_latent(self, x: torch.Tensor) -> torch.Tensor:
        prior = [p.requires_grad for p in self.parameters()]
        try:
            for p in self.parameters():
                p.requires_grad_(False)
            with torch.no_grad():
                return self.latent(x).detach()
        finally:
            for p, flag in zip(self.parameters(), prior):
                p.requires_grad_(flag)


@dataclass(frozen=True)
class CausalPretextSession:
    """One raw-tape input plane with candidate-aligned exact causal cutoffs."""
    session_id: str
    asset: str
    day: str
    event_continuous: np.ndarray
    event_categorical: np.ndarray
    receive_clock_ns: np.ndarray
    candidate_cutoffs: np.ndarray
    candidate_decision_ts_ns: np.ndarray
    candidate_rows: np.ndarray
    candidate_ids: tuple[str, ...]

    def validate(self, category_sizes: Sequence[int]) -> None:
        x = np.asarray(self.event_continuous)
        k = np.asarray(self.event_categorical)
        clock = np.asarray(self.receive_clock_ns)
        cut = np.asarray(self.candidate_cutoffs)
        decision = np.asarray(self.candidate_decision_ts_ns)
        rows = np.asarray(self.candidate_rows)
        c = len(cut)
        if (not self.session_id or self.asset not in ("HG", "NKD", "SI")
                or x.ndim != 2 or not x.shape[1]
                or k.shape != (len(x), len(category_sizes))
                or clock.shape != (len(x),) or clock.dtype != np.int64
                or cut.shape != (c,) or cut.dtype.kind not in "iu"
                or decision.shape != (c,) or decision.dtype != np.int64
                or rows.shape != (c,) or rows.dtype.kind not in "iu"
                or len(self.candidate_ids) != c):
            raise AtlasProbeRefusal("causal pretext session schema is invalid")
        if (not np.all(np.isfinite(x)) or np.any(clock[1:] < clock[:-1])
                or len(set(self.candidate_ids)) != c):
            raise AtlasProbeRefusal("causal pretext session content is invalid")
        if not np.array_equal(cut.astype(np.int64),
                              np.searchsorted(clock, decision, side="left")):
            raise AtlasProbeRefusal("pretext cutoff is not exact left searchsorted")
        for column, size in enumerate(category_sizes):
            if np.any(k[:, column] < 0) or np.any(k[:, column] >= int(size)):
                raise AtlasProbeRefusal("pretext categorical value is out of range")


class StagePretextEncoder(nn.Module):
    """Small causal mixed-event tape encoder shared by one chronology stage."""
    def __init__(self, continuous_width: int, category_sizes: Sequence[int]) -> None:
        super().__init__()
        if continuous_width < 1 or not category_sizes or any(int(x) < 2 for x in category_sizes):
            raise AtlasProbeRefusal("pretext event schema is invalid")
        self.continuous_width = int(continuous_width)
        self.category_sizes = tuple(int(x) for x in category_sizes)
        route_width = 8
        self.continuous_routes = nn.ModuleList(
            nn.Linear(1, route_width, bias=False) for _ in range(continuous_width)
        )
        self.category_embeddings = nn.ModuleList(
            nn.Embedding(size, route_width) for size in self.category_sizes
        )
        joined = route_width * (continuous_width + len(self.category_sizes))
        self.event_projection = nn.Linear(joined, 128)
        self.recurrent = nn.GRU(128, STAGE_PRETEXT_WIDTH, batch_first=True)
        self.empty_state = nn.Parameter(torch.zeros(STAGE_PRETEXT_WIDTH))
        self.head = nn.Linear(STAGE_PRETEXT_WIDTH, UNIVERSAL_OUTPUT_WIDTH)

    def event_state_chunk(
        self, continuous: torch.Tensor, categorical: torch.Tensor,
        hidden: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor | None]:
        if (continuous.ndim != 2 or continuous.shape[1] != self.continuous_width
                or categorical.shape != (len(continuous), len(self.category_sizes))
                or not bool(torch.isfinite(continuous).all())):
            raise AtlasProbeRefusal("pretext event tensor is invalid")
        pieces = [route(continuous[:, i:i + 1])
                  for i, route in enumerate(self.continuous_routes)]
        ids = categorical.to(torch.long)
        pieces.extend(embedding(ids[:, i])
                      for i, embedding in enumerate(self.category_embeddings))
        event = nn.functional.gelu(self.event_projection(torch.cat(pieces, dim=1)))
        if not len(event):
            return event.new_zeros((0, STAGE_PRETEXT_WIDTH)), hidden
        output, next_hidden = self.recurrent(event[None], hidden)
        return output[0], next_hidden

    def event_state(self, continuous: torch.Tensor, categorical: torch.Tensor) -> torch.Tensor:
        output, _ = self.event_state_chunk(continuous, categorical)
        return output

    def candidate_state(self, continuous: torch.Tensor, categorical: torch.Tensor,
                        cutoffs: torch.Tensor) -> torch.Tensor:
        event = self.event_state(continuous, categorical)
        result = self.empty_state[None].expand(len(cutoffs), -1).clone()
        live = cutoffs > 0
        if bool(live.any()):
            result[live] = event[cutoffs[live] - 1]
        return result

    def forward(self, continuous: torch.Tensor, categorical: torch.Tensor,
                cutoffs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        state = self.candidate_state(continuous, categorical, cutoffs)
        return self.head(state), state


@dataclass(frozen=True)
class PretextStreamingReceipt:
    normalizer_event_rows: int
    normalizer_chunks: int
    train_event_rows: int
    validation_event_rows: int
    encoded_event_rows: int
    train_chunks: int
    validation_chunks: int
    encoded_chunks: int
    peak_chunk_rows: int
    peak_chunk_bytes: int
    truncated_bptt_state_law: str
    device: str
    h2_permit: bool
    receipt_sha256: str


@dataclass(frozen=True)
class StagePretextCheckpoint:
    stage_id: str
    objective_id: str
    continuous_width: int
    category_sizes: tuple[int, ...]
    location: np.ndarray
    scale: np.ndarray
    constant_zero_mask: np.ndarray
    model_state: Mapping[str, np.ndarray]
    input_normalizer_sha256: str
    initialization_sha256: str
    checkpoint_sha256: str

    def load_model(self, device: str | torch.device | None = None) -> tuple[StagePretextEncoder,
                                                                            torch.device]:
        resolved = _torch_device(device)
        model = StagePretextEncoder(self.continuous_width, self.category_sizes)
        state = {name: torch.from_numpy(np.array(value, copy=True))
                 for name, value in self.model_state.items()}
        model.load_state_dict(state, strict=True)
        model.to(resolved).eval()
        for parameter in model.parameters():
            parameter.requires_grad_(False)
        return model, resolved


@dataclass(frozen=True)
class StagePretextEncoding:
    frozen_state: np.ndarray
    frozen_state_sha256: str
    receipt: PretextStreamingReceipt


@dataclass(frozen=True)
class StagePretextResult:
    stage_id: str
    frozen_state: np.ndarray
    fit_rows_sha256: str
    input_normalizer_sha256: str
    initialization_sha256: str
    checkpoint_sha256: str
    frozen_state_sha256: str
    best_epoch: int
    epoch_losses: tuple[tuple[float, float], ...]
    fit_count: int
    consumer_probe_ids: tuple[str, ...]
    consumer_mapping_sha256: str
    category_sizes: tuple[int, ...]
    objective_id: str
    checkpoint: StagePretextCheckpoint | None = None
    streaming_receipt: PretextStreamingReceipt | None = None


def _pretext_receipt(*, normalizer_event_rows: int = 0, train_event_rows: int = 0,
                     normalizer_chunks: int = 0,
                     validation_event_rows: int = 0, encoded_event_rows: int = 0,
                     train_chunks: int = 0, validation_chunks: int = 0,
                     encoded_chunks: int = 0, peak_chunk_rows: int = 0,
                     peak_chunk_bytes: int = 0, device: str = "cpu"
                     ) -> PretextStreamingReceipt:
    payload = {
        "normalizer_event_rows": int(normalizer_event_rows),
        "normalizer_chunks": int(normalizer_chunks),
        "train_event_rows": int(train_event_rows),
        "validation_event_rows": int(validation_event_rows),
        "encoded_event_rows": int(encoded_event_rows),
        "train_chunks": int(train_chunks),
        "validation_chunks": int(validation_chunks),
        "encoded_chunks": int(encoded_chunks),
        "peak_chunk_rows": int(peak_chunk_rows),
        "peak_chunk_bytes": int(peak_chunk_bytes),
        "truncated_bptt_state_law": (
            "session_ordered_chunks;hidden_carries_forward_detached;"
            "optimizer_step_per_target-bearing_chunk;no_state_across_sessions"
        ),
        "device": str(device), "h2_permit": False,
    }
    digest = _sha(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    return PretextStreamingReceipt(**payload, receipt_sha256=digest)


PretextSessionSource = (Sequence[CausalPretextSession]
                        | Callable[[], Iterable[CausalPretextSession]])


def _iter_pretext_sessions(sessions: PretextSessionSource | Iterable[CausalPretextSession],
                           category_sizes: Sequence[int]) -> Iterator[CausalPretextSession]:
    if callable(sessions):
        source = iter(sessions())
        ordered_source = True
    elif isinstance(sessions, Sequence):
        source = iter(sorted(sessions, key=lambda x: (x.asset, x.day, x.session_id)))
        ordered_source = True
    else:
        source = iter(sessions)
        ordered_source = True
    found = False; prior_key: tuple[str, str, str] | None = None
    for session in source:
        found = True
        key = (session.asset, session.day, session.session_id)
        if ordered_source and prior_key is not None and key < prior_key:
            raise AtlasProbeRefusal("streamed pretext sessions are not canonically ordered")
        prior_key = key
        day = str(session.day)
        canonical_day = (f"{day[:4]}-{day[4:6]}-{day[6:]}"
                         if len(day) == 8 and day.isdigit() else day)
        if (len(canonical_day) != 10 or canonical_day[4] != "-"
                or canonical_day[7] != "-"
                or not canonical_day.replace("-", "").isdigit()):
            raise AtlasProbeRefusal("pretext session day is not canonical")
        if canonical_day > _DEVELOPMENT_LAST_DAY:
            raise AtlasProbeRefusal("post-development/H2 pretext session is forbidden")
        session.validate(category_sizes)
        yield session
    if not found:
        raise AtlasProbeRefusal("pretext sessions are empty")


def _stream_fit_event_normalizer(
    sessions: PretextSessionSource, category_sizes: Sequence[int], train_rows: set[int],
    continuous_width: int, chunk_events: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int, int]:
    total = np.zeros(continuous_width, np.float64)
    total_square = np.zeros(continuous_width, np.float64)
    count = chunks = peak_rows = 0
    for session in _iter_pretext_sessions(sessions, category_sizes):
        candidate_rows = np.asarray(session.candidate_rows, np.int64)
        local = np.flatnonzero(np.asarray([int(row) in train_rows
                                          for row in candidate_rows], bool))
        if not len(local):
            continue
        stop = int(np.max(np.asarray(session.candidate_cutoffs, np.int64)[local]))
        for start in range(0, stop, chunk_events):
            piece = np.asarray(
                session.event_continuous[start:min(stop, start + chunk_events)], np.float64
            )
            if len(piece):
                total += piece.sum(axis=0, dtype=np.float64)
                total_square += np.einsum("ij,ij->j", piece, piece, dtype=np.float64)
                count += len(piece); chunks += 1; peak_rows = max(peak_rows, len(piece))
    if count < 1:
        raise AtlasProbeRefusal("pretext normalization has no training-prefix events")
    location = total / count
    variance = np.maximum(total_square / count - location * location, 0.0)
    scale = np.sqrt(variance)
    constant = scale == 0
    scale[constant] = 1.0
    return (_frozen_array(location), _frozen_array(scale), _frozen_array(constant),
            count, chunks, peak_rows)


def _frozen_pretext_checkpoint(
    stage_id: str, spec: ProbeSpec, model: StagePretextEncoder,
    location: np.ndarray, scale: np.ndarray, constant: np.ndarray,
    category_sizes: tuple[int, ...], normalizer_hash: str, init_hash: str,
) -> StagePretextCheckpoint:
    state = {
        name: _frozen_array(tensor.detach().cpu().numpy())
        for name, tensor in sorted(model.state_dict().items())
    }
    checkpoint_hash = _model_state_sha256(model)
    return StagePretextCheckpoint(
        stage_id, spec.probe_id, model.continuous_width, category_sizes,
        _frozen_array(location), _frozen_array(scale), _frozen_array(constant),
        MappingProxyType(state), normalizer_hash, init_hash, checkpoint_hash,
    )


def _normalized_event_chunk(
    session: CausalPretextSession, start: int, stop: int,
    checkpoint: StagePretextCheckpoint, device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, int]:
    value = ((np.asarray(session.event_continuous[start:stop], np.float64)
              - checkpoint.location) / checkpoint.scale)
    value[:, checkpoint.constant_zero_mask] = 0.0
    continuous = torch.from_numpy(value.astype(np.float32)).to(device)
    categorical = torch.from_numpy(np.asarray(
        session.event_categorical[start:stop], np.int64
    )).to(device)
    used = (continuous.numel() * continuous.element_size()
            + categorical.numel() * categorical.element_size())
    return continuous, categorical, int(used)


def encode_stage_pretext(
    checkpoint: StagePretextCheckpoint,
    sessions: PretextSessionSource | Iterable[CausalPretextSession], *, row_count: int,
    device: str | torch.device | None = None,
    chunk_events: int = _DEFAULT_STREAM_EVENTS,
) -> StagePretextEncoding:
    """Stream later sessions once through a frozen causal checkpoint."""
    chunk_events = _chunk_size(chunk_events)
    if row_count < 0:
        raise AtlasProbeRefusal("pretext encoding row count is invalid")
    model, resolved = checkpoint.load_model(device)
    state = np.full((row_count, STAGE_PRETEXT_WIDTH), np.nan, np.float32)
    seen = np.zeros(row_count, np.bool_)
    event_rows = chunks = peak_rows = peak_bytes = 0
    with torch.no_grad():
        for session in _iter_pretext_sessions(sessions, checkpoint.category_sizes):
            session_rows = np.asarray(session.candidate_rows, np.int64)
            if (np.any(session_rows < 0) or np.any(session_rows >= row_count)
                    or len(np.unique(session_rows)) != len(session_rows)
                    or np.any(seen[session_rows])):
                raise AtlasProbeRefusal("pretext encoding row ownership is invalid")
            seen[session_rows] = True
            cutoffs = np.asarray(session.candidate_cutoffs, np.int64)
            local_state = model.empty_state.detach()[None].expand(len(cutoffs), -1).clone()
            hidden = None
            stop = int(cutoffs.max(initial=0))
            for start in range(0, stop, chunk_events):
                end = min(stop, start + chunk_events)
                continuous, categorical, used = _normalized_event_chunk(
                    session, start, end, checkpoint, resolved
                )
                output, hidden = model.event_state_chunk(continuous, categorical, hidden)
                hidden = None if hidden is None else hidden.detach()
                selected = np.flatnonzero((cutoffs > start) & (cutoffs <= end))
                if len(selected):
                    at = torch.from_numpy(cutoffs[selected] - start - 1).to(resolved)
                    local_state[torch.from_numpy(selected).to(resolved)] = output[at]
                event_rows += end - start; chunks += 1; peak_rows = max(peak_rows, end - start)
                peak_bytes = max(peak_bytes, used + output.numel() * output.element_size())
            state[session_rows] = local_state.cpu().numpy()
    if not bool(seen.all()) or not np.all(np.isfinite(state)):
        raise AtlasProbeRefusal("pretext frozen state coverage is incomplete")
    state = _frozen_array(state)
    receipt = _pretext_receipt(encoded_event_rows=event_rows, encoded_chunks=chunks,
                               peak_chunk_rows=peak_rows, peak_chunk_bytes=peak_bytes,
                               device=str(resolved))
    return StagePretextEncoding(state, _sha(_array_bytes(state)), receipt)


def fit_stage_pretext(
    stage_id: str, sessions: PretextSessionSource,
    category_sizes: Sequence[int], spec: ProbeSpec, target: ProbeTarget, *,
    fit_indices: Sequence[int], consumer_probe_ids: Sequence[str],
    seed: int = 20260816, device: str | torch.device | None = None,
    chunk_events: int = _DEFAULT_STREAM_EVENTS, encode_sessions: bool = True,
) -> StagePretextResult:
    """Fit one of exactly two discarded E1 mixed-event objectives (C1/C2).

    There is no E2 pretext optimizer fit.  E2 consumes the frozen E1 states;
    checkpoints may not warm-start either shallow probes or one another.
    """
    if stage_id not in {"E1", "E1R"} or (spec.cell, spec.probe_id) not in {
        (1, "C01P01"), (2, "C02P01")
    }:
        raise AtlasProbeRefusal("pretext must be one of the two E1 mixed-event objectives")
    category_sizes = tuple(int(x) for x in category_sizes)
    chunk_events = _chunk_size(chunk_events)
    if not isinstance(sessions, Sequence) and not callable(sessions):
        raise AtlasProbeRefusal("pretext fit requires a re-iterable session source")
    widths: set[int] = set()
    n = len(target.values)
    row_day = np.empty(n, dtype="U32")
    row_id = np.empty(n, dtype="U128")
    seen = np.zeros(n, np.bool_); all_ids: set[str] = set()
    for session in _iter_pretext_sessions(sessions, category_sizes):
        widths.add(np.asarray(session.event_continuous).shape[1])
        session_rows = np.asarray(session.candidate_rows, np.int64)
        if (np.any(session_rows < 0) or np.any(session_rows >= n)
                or len(np.unique(session_rows)) != len(session_rows)
                or np.any(seen[session_rows])):
            raise AtlasProbeRefusal("pretext sessions do not own target rows exactly once")
        seen[session_rows] = True
        row_day[session_rows] = session.day
        row_id[session_rows] = session.candidate_ids
        if any(candidate_id in all_ids for candidate_id in session.candidate_ids):
            raise AtlasProbeRefusal("pretext candidate ids are duplicated")
        all_ids.update(session.candidate_ids)
    if len(widths) != 1:
        raise AtlasProbeRefusal("pretext continuous schema changes across sessions")
    if not bool(seen.all()) or len(all_ids) != n:
        raise AtlasProbeRefusal("pretext sessions do not cover target rows exactly once")
    consumers = tuple(sorted(set(str(x) for x in consumer_probe_ids)))
    if not consumers or len(consumers) != len(tuple(consumer_probe_ids)):
        raise AtlasProbeRefusal("pretext consumer mapping is empty or duplicated")
    idx = _require_frozen_indices(row_day, stage_id, fit_indices)
    if len(idx) < 2:
        raise AtlasProbeRefusal("pretext frozen fit population is too small")
    idx = idx[np.lexsort((row_id[idx], row_day[idx]))]
    unique_days = sorted(set(row_day[idx].tolist()))
    validation_days = set(unique_days[-max(1, int(np.ceil(.1 * len(unique_days)))):])
    val = idx[np.asarray([x in validation_days for x in row_day[idx]])]
    train = idx[np.asarray([x not in validation_days for x in row_day[idx]])]
    valid = np.asarray(target.validity_mask, bool)
    train_opt, val_opt = train[valid[train]], val[valid[val]]
    if not len(train_opt) or not len(val_opt):
        raise AtlasProbeRefusal("pretext train/validation support is empty")
    train_set = set(train.tolist())
    location, scale, constant, normalizer_n, normalizer_chunks, normalizer_peak = \
        _stream_fit_event_normalizer(
            sessions, category_sizes, train_set, next(iter(widths)), chunk_events
        )
    normalizer_hash = _sha(_array_bytes(location) + _array_bytes(scale) + _array_bytes(constant))
    resolved = _torch_device(device)
    torch.manual_seed(seed + spec.cell - 1)
    if resolved.type == "cuda":
        torch.cuda.manual_seed_all(seed + spec.cell - 1)
    model = StagePretextEncoder(next(iter(widths)), category_sizes).to(resolved)
    init_hash = _model_state_sha256(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best, best_epoch, stale, best_state = np.inf, -1, 0, None
    history: list[tuple[float, float]] = []
    target_before = _target_content_hash(target)
    train_rows, val_rows = set(train_opt.tolist()), set(val_opt.tolist())
    checkpoint_view = StagePretextCheckpoint(
        stage_id, spec.probe_id, next(iter(widths)), category_sizes,
        location, scale, constant, MappingProxyType({}), normalizer_hash, init_hash, "",
    )
    train_event_rows = validation_event_rows = 0
    train_chunks = validation_chunks = 0
    peak_rows = normalizer_peak
    peak_bytes = normalizer_peak * next(iter(widths)) * 8
    for epoch in range(6):
        model.train(); epoch_train: list[float] = []
        for session in _iter_pretext_sessions(sessions, category_sizes):
            local = np.asarray([i for i, row in enumerate(session.candidate_rows)
                                if int(row) in train_rows], np.int64)
            if not len(local):
                continue
            candidate_rows = np.asarray(session.candidate_rows, np.int64)
            cutoffs = np.asarray(session.candidate_cutoffs, np.int64)
            hidden = None
            stop = int(cutoffs[local].max(initial=0))
            starts = list(range(0, stop, chunk_events)) or [0]
            for start in starts:
                end = min(stop, start + chunk_events)
                selected = local[(cutoffs[local] > start) & (cutoffs[local] <= end)]
                if start == 0:
                    selected = np.r_[local[cutoffs[local] == 0], selected]
                output = None; used = 0
                if end > start:
                    continuous, categorical, used = _normalized_event_chunk(
                        session, start, end, checkpoint_view, resolved
                    )
                    output, next_hidden = model.event_state_chunk(
                        continuous, categorical, hidden
                    )
                    hidden = None if next_hidden is None else next_hidden.detach()
                    train_event_rows += end - start; train_chunks += 1
                    peak_rows = max(peak_rows, end - start)
                    peak_bytes = max(peak_bytes, used + output.numel() * output.element_size())
                if not len(selected):
                    continue
                candidate_state = model.empty_state[None].expand(len(selected), -1).clone()
                live = cutoffs[selected] > 0
                if bool(np.any(live)):
                    at = torch.from_numpy(cutoffs[selected[live]] - start - 1).to(resolved)
                    candidate_state[torch.from_numpy(np.flatnonzero(live)).to(resolved)] = output[at]
                optimizer.zero_grad(set_to_none=True)
                prediction = model.head(candidate_state)
                loss = loss_for_probe(
                    spec, prediction, _slice_target(target, candidate_rows[selected])
                )
                loss.backward()
                gradients = [p.grad for p in model.parameters() if p.grad is not None]
                if (not gradients
                        or any(not bool(torch.isfinite(g).all()) for g in gradients)
                        or sum(float(torch.sum(g * g)) for g in gradients) <= 0):
                    raise AtlasProbeRefusal("pretext gradient is zero or non-finite")
                optimizer.step(); epoch_train.append(float(loss.detach()))
        if not epoch_train:
            raise AtlasProbeRefusal("pretext executed no optimizer batch")
        model.eval(); validation_parts: list[float] = []
        with torch.no_grad():
            for session in _iter_pretext_sessions(sessions, category_sizes):
                local = np.asarray([i for i, row in enumerate(session.candidate_rows)
                                    if int(row) in val_rows], np.int64)
                if not len(local):
                    continue
                candidate_rows = np.asarray(session.candidate_rows, np.int64)
                cutoffs = np.asarray(session.candidate_cutoffs, np.int64)
                local_state = model.empty_state[None].expand(len(local), -1).clone()
                stop = int(cutoffs[local].max(initial=0)); hidden = None
                for start in range(0, stop, chunk_events):
                    end = min(stop, start + chunk_events)
                    continuous, categorical, used = _normalized_event_chunk(
                        session, start, end, checkpoint_view, resolved
                    )
                    output, hidden = model.event_state_chunk(continuous, categorical, hidden)
                    hidden = None if hidden is None else hidden.detach()
                    selected = np.flatnonzero((cutoffs[local] > start)
                                              & (cutoffs[local] <= end))
                    if len(selected):
                        at = torch.from_numpy(cutoffs[local[selected]] - start - 1).to(resolved)
                        local_state[torch.from_numpy(selected).to(resolved)] = output[at]
                    validation_event_rows += end - start; validation_chunks += 1
                    peak_rows = max(peak_rows, end - start)
                    peak_bytes = max(peak_bytes, used + output.numel() * output.element_size())
                prediction = model.head(local_state)
                validation_parts.append(float(loss_for_probe(
                    spec, prediction, _slice_target(target, candidate_rows[local]),
                    use_fit_weight=False)))
        validation = float(np.mean(validation_parts))
        train_loss = float(np.mean(epoch_train)); history.append((train_loss, validation))
        if validation < best * .999:
            best, best_epoch, stale = validation, epoch + 1, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if epoch + 1 >= 2 and stale >= 2:
            break
    if best_state is None or _target_content_hash(target) != target_before:
        raise AtlasProbeRefusal("pretext checkpoint missing or target mutated")
    model.load_state_dict(best_state, strict=True); model.eval()
    checkpoint = _frozen_pretext_checkpoint(
        stage_id, spec, model, location, scale, constant, category_sizes,
        normalizer_hash, init_hash,
    )
    if checkpoint.checkpoint_sha256 == init_hash:
        raise AtlasProbeRefusal("pretext parameters did not change")
    if encode_sessions:
        encoding = encode_stage_pretext(
            checkpoint, sessions, row_count=n, device=resolved, chunk_events=chunk_events
        )
        state, state_hash = encoding.frozen_state, encoding.frozen_state_sha256
    else:
        state = _frozen_array(np.empty((0, STAGE_PRETEXT_WIDTH), np.float32))
        state_hash = _sha(_array_bytes(state))
        encoding = StagePretextEncoding(state, state_hash, _pretext_receipt(device=str(resolved)))
    stream_receipt = _pretext_receipt(
        normalizer_event_rows=normalizer_n, normalizer_chunks=normalizer_chunks,
        train_event_rows=train_event_rows,
        validation_event_rows=validation_event_rows,
        encoded_event_rows=encoding.receipt.encoded_event_rows,
        train_chunks=train_chunks, validation_chunks=validation_chunks,
        encoded_chunks=encoding.receipt.encoded_chunks,
        peak_chunk_rows=max(peak_rows, encoding.receipt.peak_chunk_rows),
        peak_chunk_bytes=max(peak_bytes, encoding.receipt.peak_chunk_bytes),
        device=str(resolved),
    )
    consumer_hash = _sha(json.dumps({"stage": stage_id, "objective": spec.probe_id,
                                     "consumers": consumers,
                                     "checkpoint_sha256": checkpoint.checkpoint_sha256,
                                     "frozen_state_sha256": state_hash,
                                     "category_sizes": category_sizes},
                                    sort_keys=True, separators=(",", ":")).encode())
    return StagePretextResult(stage_id, state,
                              _sha(np.asarray(idx, np.int64).tobytes()), normalizer_hash,
                              init_hash, checkpoint.checkpoint_sha256, state_hash,
                              best_epoch, tuple(history), 1, consumers, consumer_hash,
                              category_sizes, spec.probe_id, checkpoint, stream_receipt)


@dataclass(frozen=True)
class ProbeRows:
    static_context: np.ndarray
    stage_pretext: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    decision_ts_ns: np.ndarray
    candidate_id: np.ndarray

    def joined(self) -> np.ndarray:
        static = np.asarray(self.static_context, dtype=np.float64)
        pretext = np.asarray(self.stage_pretext, dtype=np.float64)
        n = len(static)
        if static.shape != (n, STATIC_WIDTH) or pretext.shape != (n, PRETEXT_WIDTH):
            raise AtlasProbeRefusal("probe rows require exact 1865+1024 inputs")
        for value in (self.asset, self.day, self.decision_ts_ns, self.candidate_id):
            if np.asarray(value).shape != (n,):
                raise AtlasProbeRefusal("probe row keys are misaligned")
        result = np.concatenate((static, pretext), axis=1)
        if not np.all(np.isfinite(result)):
            raise AtlasProbeRefusal("probe rows contain non-finite input")
        return result

    def canonical_order(self, indices: Sequence[int]) -> np.ndarray:
        i = np.asarray(indices, dtype=np.int64)
        if i.ndim != 1 or np.any(i < 0) or np.any(i >= len(self.static_context)):
            raise AtlasProbeRefusal("probe indices are invalid")
        # np.lexsort uses the last key as primary.
        order = np.lexsort((np.asarray(self.candidate_id)[i].astype(str),
                            np.asarray(self.decision_ts_ns)[i].astype(np.int64),
                            np.asarray(self.day)[i].astype(str),
                            np.asarray(self.asset)[i].astype(str)))
        return i[order]


@dataclass(frozen=True)
class SharedProbePlaneReceipt:
    row_count: int
    joined_build_count: int
    normalizer_fit_count: int
    transform_count: int
    peak_host_bytes: int
    h2_permit: bool
    receipt_sha256: str


@dataclass(frozen=True)
class SharedProbePlane:
    """One target-neutral normalized plane reused by all real/twin fits."""
    rows_identity: int
    stage_id: str
    fit_indices_sha256: str
    canonical_fit_indices: np.ndarray
    train_indices: np.ndarray
    validation_indices: np.ndarray
    normalizer: FitOnlyNormalizer
    normalized: np.ndarray
    normalized_sha256: str
    receipt: SharedProbePlaneReceipt

    @classmethod
    def build(cls, rows: ProbeRows, fit_indices: Sequence[int], *,
              stage_id: str = "E1") -> "SharedProbePlane":
        frozen = _require_frozen_indices(rows.day, stage_id, fit_indices)
        idx = rows.canonical_order(frozen)
        if len(idx) < 2:
            raise AtlasProbeRefusal("shared probe plane needs at least two fit rows")
        raw_days = np.asarray(rows.day).astype(str)
        canonical_days = np.asarray([
            f"{day[:4]}-{day[4:6]}-{day[6:]}"
            if len(day) == 8 and day.isdigit() else day for day in raw_days
        ])
        if (any(len(day) != 10 or day[4] != "-" or day[7] != "-"
                or not day.replace("-", "").isdigit() for day in canonical_days)
                or np.any(canonical_days > _DEVELOPMENT_LAST_DAY)):
            raise AtlasProbeRefusal("shared probe plane cannot contain H2 rows")
        unique_days = sorted(set(raw_days[idx].tolist()))
        validation_count = max(1, int(np.ceil(.1 * len(unique_days))))
        validation_days = set(unique_days[-validation_count:])
        val_idx = idx[np.asarray([day in validation_days for day in raw_days[idx]])]
        train_idx = idx[np.asarray([day not in validation_days for day in raw_days[idx]])]
        if not len(train_idx) or not len(val_idx):
            raise AtlasProbeRefusal("chronological final-10% fit validation is empty")
        joined = rows.joined()
        normalizer = FitOnlyNormalizer.fit(joined[train_idx])
        normalized = _frozen_array(normalizer.transform(joined), np.float32)
        peak_host = int(joined.nbytes + normalized.nbytes)
        fit_hash = _sha(_array_bytes(np.asarray(idx, np.int64)))
        normalized_hash = _sha(_array_bytes(normalized))
        payload = {
            "row_count": len(normalized), "joined_build_count": 1,
            "normalizer_fit_count": 1, "transform_count": 1,
            "peak_host_bytes": peak_host, "h2_permit": False,
            "fit_indices_sha256": fit_hash,
            "normalizer_sha256": normalizer.receipt_sha256,
            "normalized_sha256": normalized_hash,
        }
        receipt_hash = _sha(json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode())
        receipt = SharedProbePlaneReceipt(
            len(normalized), 1, 1, 1, peak_host, False, receipt_hash
        )
        return cls(
            id(rows), stage_id, fit_hash, _frozen_array(idx, np.int64),
            _frozen_array(train_idx, np.int64), _frozen_array(val_idx, np.int64),
            normalizer, normalized, normalized_hash, receipt,
        )

    def require(self, rows: ProbeRows, fit_indices: Sequence[int], stage_id: str) -> None:
        if id(rows) != self.rows_identity or stage_id != self.stage_id:
            raise AtlasProbeRefusal("shared probe plane is bound to different rows/stage")
        expected = rows.canonical_order(_require_frozen_indices(
            rows.day, stage_id, fit_indices
        ))
        if (_sha(_array_bytes(np.asarray(expected, np.int64)))
                != self.fit_indices_sha256):
            raise AtlasProbeRefusal("shared probe plane fit population differs")


@dataclass(frozen=True)
class ActionFitWeightReceipt:
    schema: str
    row_count: int
    fit_row_count: int
    weighted_row_count: int
    asset_day_count: int
    apply_class_weight: bool
    class_cap: float
    optimizer_step_unit: str
    class_factors: Mapping[str, float]
    asset_day_totals: Mapping[str, float]
    fit_rows_sha256: str
    input_sha256: str
    weight_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        core = {
            "schema": self.schema, "row_count": self.row_count,
            "fit_row_count": self.fit_row_count,
            "weighted_row_count": self.weighted_row_count,
            "asset_day_count": self.asset_day_count,
            "apply_class_weight": self.apply_class_weight,
            "class_cap": self.class_cap,
            "optimizer_step_unit": self.optimizer_step_unit,
            "class_factors": dict(self.class_factors),
            "asset_day_totals": dict(self.asset_day_totals),
            "fit_rows_sha256": self.fit_rows_sha256,
            "input_sha256": self.input_sha256,
            "weight_sha256": self.weight_sha256,
        }
        expected = _sha(json.dumps(
            core, sort_keys=True, separators=(",", ":")).encode())
        if expected != self.receipt_sha256:
            raise AtlasProbeRefusal("action fit-weight receipt is not self-consistent")


def _canonical_fit_rows(fit_rows: Sequence[int] | np.ndarray, n: int) -> np.ndarray:
    raw = np.asarray(fit_rows)
    if raw.dtype == np.bool_:
        if raw.shape != (n,):
            raise AtlasProbeRefusal("fit-row mask is misaligned")
        idx = np.flatnonzero(raw).astype(np.int64)
    else:
        try:
            idx = np.asarray(fit_rows, np.int64)
            numeric = np.asarray(fit_rows, np.float64)
        except (TypeError, ValueError) as exc:
            raise AtlasProbeRefusal("fit rows are not integer indices") from exc
        if (idx.ndim != 1 or numeric.shape != idx.shape
                or not np.all(np.isfinite(numeric))
                or not np.array_equal(numeric, idx.astype(np.float64))
                or any(isinstance(value, (bool, np.bool_))
                       for value in raw.tolist())
                or len(np.unique(idx)) != len(idx)
                or np.any(idx < 0) or np.any(idx >= n)):
            raise AtlasProbeRefusal("fit rows contain duplicates or invalid indices")
    if not len(idx):
        raise AtlasProbeRefusal("fit rows are empty")
    return np.sort(idx)


def action_fit_weights(
    asset: Sequence[object], day: Sequence[object],
    action_target: Sequence[object], action_loss_mask: Sequence[bool],
    fit_rows: Sequence[int] | np.ndarray, *, apply_class_weight: bool = True,
) -> tuple[np.ndarray, ActionFitWeightReceipt]:
    """Return A-013 weights; consumers step once per complete asset-day gradient."""
    a = np.asarray(asset).astype(str); d = np.asarray(day).astype(str)
    # Object storage prevents an excluded sentinel from widening/coercing the
    # dtype of supervised FIT labels.  Only selected values are normalized.
    y = np.asarray(action_target, dtype=object)
    mask = np.asarray(action_loss_mask, bool)
    n = len(a)
    if (not n or a.shape != (n,) or d.shape != (n,) or y.shape != (n,)
            or mask.shape != (n,)):
        raise AtlasProbeRefusal("action fit-weight inputs are misaligned")
    idx = _canonical_fit_rows(fit_rows, n)
    eligible = idx[mask[idx]]
    if not len(eligible):
        raise AtlasProbeRefusal("action fit weights have no supervised fit rows")
    try:
        eligible_y = np.asarray([float(y[i]) for i in eligible], np.float64)
    except (TypeError, ValueError) as exc:
        raise AtlasProbeRefusal("supervised action fit targets are not numeric") from exc
    if not np.all(np.isfinite(eligible_y)):
        raise AtlasProbeRefusal("supervised action fit targets are not finite")
    if apply_class_weight and not np.all(np.isin(eligible_y, (0.0, 1.0))):
        raise AtlasProbeRefusal("class-weighted action targets must be binary")
    weight = np.zeros(n, dtype=np.float64)
    keys = tuple(sorted(set(zip(a[eligible].tolist(), d[eligible].tolist()))))
    for asset_day in keys:
        members = eligible[(a[eligible] == asset_day[0])
                           & (d[eligible] == asset_day[1])]
        weight[members] = 1.0 / len(members)
    class_factors: dict[str, float] = {}
    if apply_class_weight:
        counts = {level: int(np.sum(eligible_y == level)) for level in (0, 1)}
        if not all(counts.values()):
            raise AtlasProbeRefusal("action fit weights require both pooled classes")
        largest = max(counts.values())
        factors = {level: min(4.0, largest / counts[level]) for level in (0, 1)}
        for level, factor in factors.items():
            members = eligible[eligible_y == level]
            weight[members] *= factor
            class_factors[str(level)] = float(factor)
        for asset_day in keys:
            members = eligible[(a[eligible] == asset_day[0])
                               & (d[eligible] == asset_day[1])]
            total = float(weight[members].sum())
            if total <= 0:
                raise AtlasProbeRefusal("action asset-day has zero fit weight")
            weight[members] /= total
    frozen = np.ascontiguousarray(weight, np.float32); frozen.setflags(write=False)
    totals = {f"{asset_name}|{day_name}": float(frozen[
        eligible[(a[eligible] == asset_name) & (d[eligible] == day_name)]].sum())
        for asset_name, day_name in keys}
    if any(not np.isclose(value, 1.0, rtol=0.0, atol=1e-6)
           for value in totals.values()):
        raise AtlasProbeRefusal("action fit asset-day weight does not sum to one")
    fit_hash = _sha(_array_bytes(idx))
    normalized_targets = []
    for index in idx:
        if not mask[index]:
            normalized_targets.append(None)
            continue
        try:
            value = float(y[index])
        except (TypeError, ValueError) as exc:
            raise AtlasProbeRefusal("supervised action fit targets are not numeric") from exc
        if not np.isfinite(value):
            raise AtlasProbeRefusal("supervised action fit targets are not finite")
        normalized_targets.append(value)
    input_hash = _sha(json.dumps({
        "asset": a[idx].tolist(), "day": d[idx].tolist(),
        "action_target": normalized_targets,
        "action_loss_mask": mask[idx].astype(np.uint8).tolist(),
    }, sort_keys=True, separators=(",", ":")).encode())
    weight_hash = _sha(_array_bytes(frozen))
    core = {
        "schema": "entry-v2-action-fit-weights-v1", "row_count": n,
        "fit_row_count": len(idx), "weighted_row_count": len(eligible),
        "asset_day_count": len(keys), "apply_class_weight": bool(apply_class_weight),
        "class_cap": 4.0, "optimizer_step_unit": "complete_asset_day_gradient",
        "class_factors": class_factors,
        "asset_day_totals": totals, "fit_rows_sha256": fit_hash,
        "input_sha256": input_hash, "weight_sha256": weight_hash,
    }
    receipt_hash = _sha(json.dumps(core, sort_keys=True, separators=(",", ":")).encode())
    receipt = ActionFitWeightReceipt(
        core["schema"], n, len(idx), len(eligible), len(keys),
        bool(apply_class_weight), 4.0, "complete_asset_day_gradient",
        MappingProxyType(class_factors),
        MappingProxyType(totals), fit_hash, input_hash, weight_hash, receipt_hash)
    return frozen, receipt


def asset_day_fit_weights(
    asset: Sequence[object], day: Sequence[object], target: Sequence[object],
    loss_mask: Sequence[bool], fit_rows: Sequence[int] | np.ndarray, *,
    apply_class_weight: bool = False,
) -> tuple[np.ndarray, ActionFitWeightReceipt]:
    """Generic seam: base day weights by default, capped binary weights on request."""
    return action_fit_weights(
        asset, day, target, loss_mask, fit_rows,
        apply_class_weight=apply_class_weight)


@dataclass(frozen=True)
class CanonicalPhasePairManifest:
    indices: np.ndarray
    group_ids: np.ndarray
    pairs: tuple[tuple[int, int], ...]
    pair_weights: np.ndarray
    candidate_index_pairs: tuple[tuple[int, int], ...]
    candidate_id_pairs: tuple[tuple[str, str], ...]
    nearest_time_diagnostic_ids: Mapping[str, tuple[str, ...]]
    group_count: int
    asset_day_count: int
    pairable_positive_count: int
    fit_rows_sha256: str
    fit_input_sha256: str
    receipt_sha256: str


def canonical_phase_pair_manifest(
    candidate_id: Sequence[object], asset: Sequence[object], day: Sequence[object],
    phase: Sequence[object], decision_ts: Sequence[int],
    action_target: Sequence[object], action_loss_mask: Sequence[bool],
    fit_rows: Sequence[int] | np.ndarray,
) -> CanonicalPhasePairManifest:
    """Build every supervised same-(asset, day, phase) positive-negative pair."""
    cid = np.asarray(candidate_id).astype(str); a = np.asarray(asset).astype(str)
    d = np.asarray(day).astype(str); ph = np.asarray(phase).astype(str)
    ts = np.asarray(decision_ts); y = np.asarray(action_target, dtype=object)
    mask = np.asarray(action_loss_mask, bool); n = len(cid)
    if (not n or any(value.shape != (n,) for value in (a, d, ph, ts, y, mask))
            or len(set(cid.tolist())) != n or ts.dtype.kind not in "iu"):
        raise AtlasProbeRefusal("phase-pair inputs are invalid or misaligned")
    idx = _canonical_fit_rows(fit_rows, n)
    supervised = idx[mask[idx]]
    try:
        supervised_y = np.asarray([float(y[i]) for i in supervised], np.float64)
    except (TypeError, ValueError) as exc:
        raise AtlasProbeRefusal("phase-pair fit labels must be binary") from exc
    if (not np.all(np.isfinite(supervised_y))
            or not np.all(np.isin(supervised_y, (0.0, 1.0)))):
        raise AtlasProbeRefusal("phase-pair fit labels must be binary")
    normalized_y = np.full(n, np.nan, np.float64)
    normalized_y[supervised] = supervised_y
    ordered = sorted(supervised.tolist(), key=lambda i: (
        a[i], d[i], ph[i], int(ts[i]), cid[i]))
    grouped: dict[tuple[str, str, str], list[int]] = {}
    for index in ordered:
        grouped.setdefault((a[index], d[index], ph[index]), []).append(index)
    pairable = {key: members for key, members in grouped.items()
                if any(bool(normalized_y[i]) for i in members)
                and any(not bool(normalized_y[i]) for i in members)}
    pairable_positive_by_day: dict[tuple[str, str], int] = {}
    for key, members in pairable.items():
        asset_day = key[:2]
        pairable_positive_by_day[asset_day] = (
            pairable_positive_by_day.get(asset_day, 0)
            + sum(bool(normalized_y[i]) for i in members))
    flat: list[int] = []; group_ids: list[int] = []
    for group_number, key in enumerate(sorted(pairable)):
        members = pairable[key]
        flat.extend(members); group_ids.extend([group_number] * len(members))
    local = {global_index: local_index for local_index, global_index in enumerate(flat)}
    pairs: list[tuple[int, int]] = []
    global_pairs: list[tuple[int, int]] = []
    id_pairs: list[tuple[str, str]] = []
    pair_weights: list[float] = []
    nearest: dict[str, tuple[str, ...]] = {}
    for key in sorted(pairable):
        members = pairable[key]
        positives = [i for i in members if bool(normalized_y[i])]
        negatives = [i for i in members if not bool(normalized_y[i])]
        positive_count = pairable_positive_by_day[key[:2]]
        for positive in positives:
            diagnostic = sorted(negatives, key=lambda negative: (
                abs(int(ts[negative]) - int(ts[positive])), int(ts[negative]),
                cid[negative]))[:4]
            nearest[cid[positive]] = tuple(cid[index] for index in diagnostic)
            pair_weight = 1.0 / (len(negatives) * positive_count)
            for negative in negatives:
                pairs.append((local[positive], local[negative]))
                global_pairs.append((positive, negative))
                id_pairs.append((cid[positive], cid[negative]))
                pair_weights.append(pair_weight)
    indices = np.ascontiguousarray(flat, np.int64)
    groups = np.ascontiguousarray(group_ids, np.int64)
    weights = np.ascontiguousarray(pair_weights, np.float64)
    for value in (indices, groups, weights):
        value.setflags(write=False)
    by_day_weight: dict[tuple[str, str], float] = {}
    for (positive, _negative), weight in zip(global_pairs, weights):
        key = (a[positive], d[positive])
        by_day_weight[key] = by_day_weight.get(key, 0.0) + float(weight)
    if any(not np.isclose(value, 1.0, rtol=0.0, atol=1e-12)
           for value in by_day_weight.values()):
        raise AtlasProbeRefusal("phase-pair asset-day weights do not sum to one")
    fit_hash = _sha(_array_bytes(idx))
    fit_input_hash = _sha(json.dumps({
        "candidate_id": cid[idx].tolist(), "asset": a[idx].tolist(),
        "day": d[idx].tolist(), "phase": ph[idx].tolist(),
        "decision_ts": [int(ts[i]) for i in idx],
        "action_target": [float(normalized_y[i]) if mask[i] else None
                          for i in idx],
        "action_loss_mask": mask[idx].astype(np.uint8).tolist(),
    }, sort_keys=True, separators=(",", ":")).encode())
    core = {
        "schema": "entry-v2-canonical-phase-pairs-v1",
        "fit_rows_sha256": fit_hash, "fit_input_sha256": fit_input_hash,
        "candidate_ids": cid[indices].tolist(), "group_ids": groups.tolist(),
        "pairs": pairs, "candidate_index_pairs": global_pairs,
        "candidate_id_pairs": id_pairs, "pair_weights": weights.tolist(),
        "nearest_time_diagnostic_ids": nearest, "nearest_k": 4,
        "group_count": len(pairable),
        "asset_day_count": len(pairable_positive_by_day),
        "pairable_positive_count": sum(pairable_positive_by_day.values()),
    }
    receipt = _sha(json.dumps(core, sort_keys=True, separators=(",", ":")).encode())
    return CanonicalPhasePairManifest(
        indices, groups, tuple(pairs), weights, tuple(global_pairs), tuple(id_pairs),
        MappingProxyType(nearest), len(pairable), len(pairable_positive_by_day),
        sum(pairable_positive_by_day.values()), fit_hash, fit_input_hash, receipt)


def fit_weights(rows: ProbeRows, target: ProbeTarget, fit_indices: Sequence[int], *,
                apply_class_weight: bool = True) -> tuple[np.ndarray, str]:
    n = len(rows.static_context)
    valid = np.asarray(target.validity_mask, dtype=bool)
    if valid.shape != (n,):
        raise AtlasProbeRefusal("target is not row-aligned")
    y = np.asarray(target.values)[:, 0]
    idx = _canonical_fit_rows(fit_indices, n)
    observed = y[idx[valid[idx]]]
    binary = bool(len(np.unique(observed)) == 2
                  and set(np.unique(observed).tolist()) <= {0.0, 1.0})
    weights, receipt = action_fit_weights(
        rows.asset, rows.day, y, valid, idx,
        apply_class_weight=bool(apply_class_weight and binary))
    return weights, receipt.receipt_sha256


def _target_content_hash(target: ProbeTarget) -> str:
    chunks: list[bytes] = []
    for name in target.__dataclass_fields__:
        value = getattr(target, name)
        if isinstance(value, np.ndarray):
            chunks.extend((name.encode(), _array_bytes(value)))
        else:
            chunks.extend((name.encode(), repr(value).encode()))
    return _sha(b"".join(chunks))


def _slice_target(target: ProbeTarget, indices: Sequence[int], *,
                  fit_weight: np.ndarray | None = None) -> ProbeTarget:
    """Slice every candidate-aligned ProbeTarget field as one atomic law."""
    idx = np.asarray(indices, dtype=np.int64)
    n = len(target.values)
    changes: dict[str, np.ndarray] = {}
    for name in target.__dataclass_fields__:
        value = getattr(target, name)
        if isinstance(value, np.ndarray) and value.ndim >= 1 and value.shape[0] == n:
            changes[name] = np.asarray(value)[idx]
    if fit_weight is not None:
        weight = np.asarray(fit_weight)
        changes["fit_weight"] = weight[idx]
    return replace(target, **changes)


@dataclass(frozen=True)
class EpochReceipt:
    epoch: int
    train_loss: float
    validation_loss: float
    component_losses: Mapping[str, float]
    gradient_norm: float
    parameter_delta: float
    checkpoint_sha256: str


@dataclass(frozen=True)
class ProbeFitResult:
    model: AtlasProbeNet
    normalizer: FitOnlyNormalizer
    latent: np.ndarray
    epochs: tuple[EpochReceipt, ...]
    best_epoch: int
    initialization_sha256: str
    best_checkpoint_sha256: str
    batch_order_sha256: str
    weight_receipt_sha256: str
    initial_validation_loss: float
    best_validation_loss: float
    shared_plane_receipt_sha256: str = ""
    device: str = "cpu"
    peak_device_batch_rows: int = 0


def _probe_validation_loss(
    model: AtlasProbeNet, spec: ProbeSpec, normalized: np.ndarray,
    indices: np.ndarray, target: ProbeTarget, batch_size: int,
    device: torch.device,
) -> float:
    """Evaluate a checkpoint on valid rows with *no* fit-time weighting.

    Asset/day and class weights are an optimizer law only.  Reusing them for
    early stopping lets a target-specific weighting scheme choose the
    checkpoint and makes real/twin comparisons incomparable.  Every valid
    validation row therefore has weight one here; invalid rows remain zero.
    """
    total = mass_total = 0.0
    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch = indices[start:start + batch_size]
            x = torch.from_numpy(np.array(normalized[batch], copy=True)).to(device)
            batch_target = _slice_target(target, batch)
            valid = np.asarray(batch_target.validity_mask, bool)
            unit_weight = np.zeros(len(valid), np.float32)
            unit_weight[valid] = 1.0
            unit_weight.setflags(write=False)
            unweighted_target = replace(batch_target, fit_weight=unit_weight)
            loss = float(loss_for_probe(spec, model(x), unweighted_target))
            mass = float(np.sum(valid))
            total += loss * mass; mass_total += mass
    if mass_total <= 0:
        raise AtlasProbeRefusal("probe validation executed no valid row")
    return total / mass_total


def fit_probe(
    spec: ProbeSpec, rows: ProbeRows, target: ProbeTarget, *,
    fit_indices: Sequence[int], initialization: AtlasProbeNet,
    learning_rate: float = 1e-3, batch_size: int = 256,
    max_epochs: int = 6, patience: int = 2, minimum_epochs: int = 2,
    relative_improvement: float = .001,
    stage_id: str = "E1",
    shared_plane: SharedProbePlane | None = None,
    device: str | torch.device | None = None,
) -> ProbeFitResult:
    if (max_epochs, patience, minimum_epochs, relative_improvement) != (6, 2, 2, .001):
        raise AtlasProbeRefusal("probe optimizer budget differs from the frozen law")
    if batch_size < 1:
        raise AtlasProbeRefusal("probe minibatch size must be positive")
    plane = (SharedProbePlane.build(rows, fit_indices, stage_id=stage_id)
             if shared_plane is None else shared_plane)
    plane.require(rows, fit_indices, stage_id)
    idx = plane.canonical_fit_indices
    target_before = _target_content_hash(target)
    train_idx, val_idx = plane.train_indices, plane.validation_indices
    target_valid = np.asarray(target.validity_mask, dtype=bool)
    train_opt_idx = train_idx[target_valid[train_idx]]
    val_opt_idx = val_idx[target_valid[val_idx]]
    if not len(train_opt_idx) or not len(val_opt_idx):
        raise AtlasProbeRefusal("probe has no available train or fit-validation target")
    normalizer = plane.normalizer
    normalized = plane.normalized
    weights, weight_hash = fit_weights(rows, target, train_opt_idx)
    weighted_target = replace(target, fit_weight=weights)
    resolved = _torch_device(device)
    model = AtlasProbeNet()
    model.strict_load_initialization(initialization)
    model.to(resolved)
    init_hash = model.canonical_state_sha256
    init_vector = torch.cat([p.detach().flatten().cpu() for p in model.parameters()])
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    # `_probe_validation_loss` constructs immutable unit row weights.  Keep
    # the original target here so no TRAIN-derived factor can reach selection.
    validation_target = target
    initial_validation_loss = _probe_validation_loss(
        model, spec, normalized, val_opt_idx, validation_target, batch_size, resolved
    )
    best_loss, best_epoch, stale, best_state = np.inf, -1, 0, None
    receipts: list[EpochReceipt] = []
    # Receipt binds the canonical schedule itself, not the number of epochs
    # traversed before target-specific early stopping.
    batch_digest = hashlib.sha256(np.asarray(train_opt_idx, np.int64).tobytes())
    batch_digest.update(json.dumps({"batch_size": batch_size, "max_epochs": max_epochs},
                                   sort_keys=True).encode())
    prior_best = np.inf
    for epoch in range(max_epochs):
        model.train(); epoch_losses: list[float] = []; grad_sq = 0.0
        for start in range(0, len(train_opt_idx), batch_size):
            batch = train_opt_idx[start:start + batch_size]
            optimizer.zero_grad(set_to_none=True)
            x = torch.from_numpy(np.array(normalized[batch], copy=True)).to(resolved)
            prediction = model(x)
            batch_target = _slice_target(weighted_target, batch)
            loss = loss_for_probe(spec, prediction, batch_target)
            loss.backward()
            batch_grad = 0.0
            for parameter in model.parameters():
                if parameter.grad is not None:
                    if not bool(torch.isfinite(parameter.grad).all()):
                        raise AtlasProbeRefusal("probe gradient is non-finite")
                    batch_grad += float(torch.sum(parameter.grad.detach() ** 2))
            if batch_grad <= 0:
                raise AtlasProbeRefusal("probe gradient is zero")
            grad_sq += batch_grad
            optimizer.step(); epoch_losses.append(float(loss.detach()))
        model.eval()
        val_loss = _probe_validation_loss(
            model, spec, normalized, val_opt_idx, validation_target,
            batch_size, resolved,
        )
        vector = torch.cat([p.detach().flatten().cpu() for p in model.parameters()])
        delta = float(torch.linalg.vector_norm(vector - init_vector))
        checkpoint = model.canonical_state_sha256
        receipts.append(EpochReceipt(epoch + 1, float(np.mean(epoch_losses)), val_loss,
                                     {spec.loss_id: float(np.mean(epoch_losses))},
                                     float(np.sqrt(grad_sq)), delta, checkpoint))
        improved = val_loss < best_loss * (1.0 - relative_improvement)
        if improved:
            best_loss, best_epoch, stale = val_loss, epoch + 1, 0
            best_state = copy.deepcopy(model.state_dict())
        else:
            stale += 1
        if best_loss > prior_best:
            raise AtlasProbeRefusal("best validation loss rose")
        prior_best = best_loss
        if epoch + 1 >= minimum_epochs and stale >= patience:
            break
    if best_state is None or best_epoch < 1:
        raise AtlasProbeRefusal("probe produced no checkpoint")
    model.load_state_dict(best_state, strict=True)
    if not receipts or max(r.parameter_delta for r in receipts) <= 0:
        raise AtlasProbeRefusal("probe parameters did not change")
    if _target_content_hash(target) != target_before:
        raise AtlasProbeRefusal("probe target or mask mutated during fit")
    model.eval()
    latent = np.empty((len(normalized), 128), np.float32)
    with torch.no_grad():
        for start in range(0, len(normalized), batch_size):
            stop = min(len(normalized), start + batch_size)
            x = torch.from_numpy(np.array(normalized[start:stop], copy=True)).to(resolved)
            latent[start:stop] = model.frozen_latent(x).cpu().numpy()
    latent = _frozen_array(latent)
    model.cpu()
    for module in (model.layer_norm, model.linear_256, model.linear_128):
        for parameter in module.parameters():
            parameter.requires_grad_(False)
    model.eval()
    return ProbeFitResult(model, normalizer, latent, tuple(receipts), best_epoch,
                          init_hash, model.canonical_state_sha256,
                          batch_digest.hexdigest(), weight_hash,
                          initial_validation_loss, float(best_loss),
                          plane.receipt.receipt_sha256, str(resolved),
                          min(batch_size, len(normalized)))


@dataclass(frozen=True)
class ProbeRehearsalResult:
    real: ProbeFitResult
    twin: ProbeFitResult
    real_relative_improvement: float
    real_minus_twin_best_loss: float
    competence_fit_count: int
    receipt_sha256: str


def rehearse_real_vs_recipient_fixed_twin(
    real_spec: ProbeSpec, twin_spec: ProbeSpec, rows: ProbeRows,
    real_target: ProbeTarget, twin_target: ProbeTarget, *,
    fit_indices: Sequence[int], initialization: AtlasProbeNet,
    learning_rate: float = 1e-3,
    shared_plane: SharedProbePlane | None = None,
    device: str | torch.device | None = None,
) -> ProbeRehearsalResult:
    """Discarded real-fit rehearsal proving skill beyond its frozen null twin."""
    if not twin_spec.shuffled_twin or real_spec.shuffled_twin:
        raise AtlasProbeRefusal("rehearsal requires one real probe and its shuffled twin")
    if real_target.probe_id != real_spec.probe_id or twin_target.probe_id != twin_spec.probe_id:
        raise AtlasProbeRefusal("rehearsal target/spec identity differs")
    fixed_fields = (
        "coordinate_mask", "coordinate_at_risk", "coordinate_censor",
        "validity_mask", "at_risk_mask", "censor_mask", "group_id", "group_size",
    )
    if any(not np.array_equal(getattr(real_target, name), getattr(twin_target, name))
           for name in fixed_fields):
        raise AtlasProbeRefusal("recipient-fixed twin changed masks or group structure")
    if np.array_equal(real_target.values, twin_target.values):
        raise AtlasProbeRefusal("recipient-fixed twin is byte-identical to real target")
    real = fit_probe(real_spec, rows, real_target, fit_indices=fit_indices,
                     initialization=initialization, learning_rate=learning_rate,
                     shared_plane=shared_plane, device=device)
    twin = fit_probe(twin_spec, rows, twin_target, fit_indices=fit_indices,
                     initialization=initialization, learning_rate=learning_rate,
                     shared_plane=shared_plane, device=device)
    if real.batch_order_sha256 != twin.batch_order_sha256:
        raise AtlasProbeRefusal("real/twin rehearsal batch schedules differ")
    denominator = max(abs(real.initial_validation_loss), 1e-12)
    improvement = (real.initial_validation_loss - real.best_validation_loss) / denominator
    separation = real.best_validation_loss - twin.best_validation_loss
    if improvement < .01 or separation >= 0:
        raise AtlasProbeRefusal("real probe did not learn beyond recipient-fixed twin")
    payload = {
        "real_probe": real_spec.probe_id, "twin_probe": twin_spec.probe_id,
        "real_initial": real.initial_validation_loss,
        "real_best": real.best_validation_loss, "twin_best": twin.best_validation_loss,
        "relative_improvement": improvement, "separation": separation,
        "real_checkpoint": real.best_checkpoint_sha256,
        "twin_checkpoint": twin.best_checkpoint_sha256,
        "competence_fit_count": 2,
    }
    return ProbeRehearsalResult(real, twin, improvement, separation, 2,
                                _sha(json.dumps(payload, sort_keys=True).encode()))


@dataclass(frozen=True)
class PositiveSlopePlatt:
    slope: float
    intercept: float
    fit_ids_sha256: str
    parameter_sha256: str

    def predict(self, score: np.ndarray) -> np.ndarray:
        return expit(self.slope * np.asarray(score, np.float64) + self.intercept)


class FrozenLogisticBindingMapper:
    """Fixed L2 logistic binding mapper followed by monotone Platt scaling."""
    def __init__(self, l2: float = 1.0, max_iterations: int = 100) -> None:
        if l2 != 1.0 or max_iterations != 100:
            raise AtlasProbeRefusal("binding mapper hyperparameters differ")
        self.l2, self.max_iterations = l2, max_iterations
        self.coef_: np.ndarray | None = None
        self.intercept_: float | None = None
        self.fit_ids_sha256: str | None = None
        self.weight_receipt_sha256: str | None = None
        self._fit_ids: frozenset[str] = frozenset()
        self.calibrator: PositiveSlopePlatt | None = None

    def fit(self, latent: np.ndarray, action: Sequence[int], mask: Sequence[bool],
            row_ids: Sequence[str], *, sample_weight: Sequence[float] | None = None,
            weight_receipt_sha256: str | None = None,
            ) -> "FrozenLogisticBindingMapper":
        x = np.asarray(latent, np.float64); y = np.asarray(action, np.float64)
        m = np.asarray(mask, bool); ids = np.asarray(row_ids, str)
        if x.ndim != 2 or x.shape[1] != 128 or y.shape != (len(x),) or m.shape != y.shape or ids.shape != y.shape:
            raise AtlasProbeRefusal("binding action inputs are misaligned")
        if (sample_weight is None) != (weight_receipt_sha256 is None):
            raise AtlasProbeRefusal("binding mapper weights and receipt must be supplied together")
        if sample_weight is None:
            weights = np.ones(len(x), np.float64)
        else:
            weights = np.asarray(sample_weight, np.float64)
            if (weights.shape != (len(x),) or not np.all(np.isfinite(weights))
                    or np.any(weights < 0) or float(weights[m].sum()) <= 0
                    or not isinstance(weight_receipt_sha256, str)
                    or len(weight_receipt_sha256) != 64
                    or any(char not in "0123456789abcdef"
                           for char in weight_receipt_sha256)):
                raise AtlasProbeRefusal("binding mapper fit weights are invalid")
        x, y, ids, weights = x[m], y[m], ids[m], weights[m]
        if len(np.unique(y)) != 2 or not np.all(np.isin(y, [0, 1])) or not np.all(np.isfinite(x)):
            raise AtlasProbeRefusal("binding mapper needs finite two-class fit data")
        def objective(theta: np.ndarray):
            z = x @ theta[:-1] + theta[-1]
            point_loss = np.logaddexp(0, z) - y * z
            loss = weights @ point_loss + .5 * self.l2 * (theta[:-1] @ theta[:-1])
            error = weights * (expit(z) - y)
            gradient = np.r_[x.T @ error + self.l2 * theta[:-1], error.sum()]
            return float(loss), gradient
        result = minimize(objective, np.zeros(x.shape[1] + 1), jac=True, method="L-BFGS-B",
                          options={"maxiter": self.max_iterations, "ftol": 1e-12})
        if not result.success or not np.all(np.isfinite(result.x)):
            raise AtlasProbeRefusal("binding logistic optimization failed")
        self.coef_, self.intercept_ = result.x[:-1].copy(), float(result.x[-1])
        if weight_receipt_sha256 is None:
            self.fit_ids_sha256 = _sha("\n".join(ids.tolist()).encode())
        else:
            self.fit_ids_sha256 = _sha(json.dumps({
                "ids": ids.tolist(), "weight_receipt_sha256": weight_receipt_sha256,
                "used_weights_sha256": _sha(_array_bytes(weights)),
            }, sort_keys=True, separators=(",", ":")).encode())
        self.weight_receipt_sha256 = weight_receipt_sha256
        self._fit_ids = frozenset(ids.tolist())
        return self

    @property
    def parameter_sha256(self) -> str:
        if self.coef_ is None:
            raise AtlasProbeRefusal("binding mapper is not fitted")
        payload = (_array_bytes(self.coef_)
                   + _array_bytes(np.asarray([self.intercept_])))
        if self.weight_receipt_sha256 is not None:
            payload += self.weight_receipt_sha256.encode()
        return _sha(payload)

    def raw_score(self, latent: np.ndarray) -> np.ndarray:
        if self.coef_ is None or self.intercept_ is None:
            raise AtlasProbeRefusal("binding mapper is not fitted")
        x = np.asarray(latent, np.float64)
        if x.ndim != 2 or x.shape[1] != 128 or not np.all(np.isfinite(x)):
            raise AtlasProbeRefusal("binding prediction latent is invalid")
        return x @ self.coef_ + self.intercept_

    def calibrate(self, latent: np.ndarray, action: Sequence[int], calibration_ids: Sequence[str],
                  *, threshold_selection_ids: Sequence[str]) -> PositiveSlopePlatt:
        ids = np.asarray(calibration_ids, str); threshold_ids = np.asarray(threshold_selection_ids, str)
        if set(ids.tolist()) & set(threshold_ids.tolist()):
            raise AtlasProbeRefusal("calibration and threshold-selection rows overlap")
        if set(ids.tolist()) & self._fit_ids or set(threshold_ids.tolist()) & self._fit_ids:
            raise AtlasProbeRefusal("fit, calibration, and threshold-selection rows overlap")
        if self.fit_ids_sha256 is None:
            raise AtlasProbeRefusal("binding mapper is not fitted")
        score = self.raw_score(latent); y = np.asarray(action, np.float64)
        if y.shape != score.shape or ids.shape != score.shape or len(np.unique(y)) != 2:
            raise AtlasProbeRefusal("calibration inputs are invalid")
        # slope=softplus(theta) makes the fitted calibration monotone increasing.
        def objective(theta: np.ndarray):
            slope = np.logaddexp(0.0, theta[0])
            z = slope * score + theta[1]
            return float(np.logaddexp(0, z).sum() - y @ z)
        result = minimize(objective, np.asarray([0.0, 0.0]), method="L-BFGS-B",
                          options={"maxiter": 100, "ftol": 1e-12})
        if not result.success or not np.all(np.isfinite(result.x)):
            raise AtlasProbeRefusal("monotone Platt optimization failed")
        slope = float(np.logaddexp(0.0, result.x[0])); intercept = float(result.x[1])
        # A softplus slope is positive by construction, so "slope > 0" is a
        # vacuous law: a numerically constant calibrator (measured slope
        # 5.34e-11, calibrated probability spread 2.6e-09) satisfies it while
        # selecting among thresholds separated by 1e-11 and publishing the
        # result as an economic winner.  Require an economically real slope
        # and a real calibrated spread over the observed score range.
        spread = float(np.ptp(expit(slope * score + intercept))) if len(score) else 0.0
        if not slope >= 1e-6 or not spread >= 1e-6:
            raise AtlasProbeRefusal(
                "DEGENERATE_CALIBRATOR: monotone Platt calibrator is numerically "
                f"constant (slope={slope!r}, calibrated_spread={spread!r})"
            )
        fit_hash = _sha("\n".join(ids.tolist()).encode())
        parameter_hash = _sha(_array_bytes(np.asarray([slope, intercept])))
        self.calibrator = PositiveSlopePlatt(slope, intercept, fit_hash, parameter_hash)
        return self.calibrator

    def predict(self, latent: np.ndarray) -> tuple[np.ndarray, Mapping[str, str]]:
        if self.calibrator is None:
            raise AtlasProbeRefusal("binding mapper has not been calibrated")
        probability = self.calibrator.predict(self.raw_score(latent))
        hashes = {"mapper_sha256": self.parameter_sha256,
                  "mapper_fit_ids_sha256": str(self.fit_ids_sha256),
                  "calibrator_sha256": self.calibrator.parameter_sha256,
                  "calibration_ids_sha256": self.calibrator.fit_ids_sha256}
        if self.weight_receipt_sha256 is not None:
            hashes["weight_receipt_sha256"] = self.weight_receipt_sha256
        return probability, hashes


@dataclass(frozen=True)
class CompetenceResult:
    steps: int
    auroc_by_asset: Mapping[str, float]
    ap_by_asset: Mapping[str, float]
    bce: float
    trunk_gradient_seen: bool
    head_gradient_seen: bool


def synthetic_competence(seed: int = 20260816, maximum_steps: int = 400) -> CompetenceResult:
    """Discarded balanced optimization proof; never returns a checkpoint."""
    if maximum_steps != 400:
        raise AtlasProbeRefusal("competence budget differs")
    rng = np.random.default_rng(seed); assets = ("HG", "NKD", "SI")
    n_asset = 64; n = n_asset * len(assets)
    y = np.tile(np.r_[np.zeros(32), np.ones(32)], len(assets)).astype(np.float32)
    x = rng.normal(0, .05, size=(n, INPUT_WIDTH)).astype(np.float32)
    x[:, 0] = (2 * y - 1) * 4.0
    torch.manual_seed(seed)
    model = AtlasProbeNet(); optimizer = torch.optim.Adam(model.parameters(), lr=3e-3)
    tx, ty = torch.from_numpy(x), torch.from_numpy(y)
    trunk_seen = head_seen = False
    for step in range(1, maximum_steps + 1):
        optimizer.zero_grad(set_to_none=True)
        logits = model(tx)[:, 0]
        loss = nn.functional.binary_cross_entropy_with_logits(logits, ty)
        loss.backward()
        trunk_seen |= model.linear_256.weight.grad is not None and bool(model.linear_256.weight.grad.abs().sum() > 0)
        head_seen |= model.head.weight.grad is not None and bool(model.head.weight.grad.abs().sum() > 0)
        optimizer.step()
        with torch.no_grad(): probability = torch.sigmoid(model(tx)[:, 0]).numpy()
        auroc = {}; ap = {}
        for i, asset in enumerate(assets):
            sl = slice(i * n_asset, (i + 1) * n_asset)
            auroc[asset] = float(roc_auc_score(y[sl], probability[sl]))
            ap[asset] = float(average_precision_score(y[sl], probability[sl]))
        bce = float(log_loss(y, probability, labels=[0, 1]))
        if min(auroc.values()) >= .995 and min(ap.values()) >= .995 and bce <= .02:
            return CompetenceResult(step, auroc, ap, bce, trunk_seen, head_seen)
    raise AtlasProbeRefusal("synthetic competence thresholds were not reached")


__all__ = [
    "ActionFitWeightReceipt", "AtlasProbeNet", "AtlasProbeRefusal",
    "CanonicalPhasePairManifest", "CausalPretextSession", "CompetenceResult", "EpochReceipt",
    "FitOnlyNormalizer", "FrozenLogisticBindingMapper", "INPUT_WIDTH",
    "PRETEXT_WIDTH", "STAGE_PRETEXT_WIDTH", "PositiveSlopePlatt", "ProbeFitResult", "ProbeRehearsalResult", "ProbeRows",
    "STATIC_WIDTH", "StagePretextEncoder", "StagePretextResult",
    "UNIVERSAL_OUTPUT_WIDTH", "action_fit_weights", "asset_day_fit_weights",
    "canonical_phase_pair_manifest", "fit_probe", "fit_stage_pretext", "fit_weights",
    "rehearse_real_vs_recipient_fixed_twin", "synthetic_competence",
]
