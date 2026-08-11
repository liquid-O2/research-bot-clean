"""train.py — the A2 training driver: ONE arm x ONE fold per invocation.

SPEC (verbatim law): TASK CARD V4 §5 (A1 losses), §6 (fold walls),
FINAL_PLAN APPENDIX C7 ("one file per arm family; manifest + mmap features;
torch.use_deterministic_algorithms(True), TF32 off, CUBLAS_WORKSPACE_CONFIG=
:4096:8, seed 20260810; one chronological session per optimizer step
(micro-batch + accumulation where needed); controls = flag variants of the SAME
script; outputs logits + loss curves (train + inner-val receipt) + GPU receipt +
config hash").

A2, verbatim: "seed 20260810, AdamW 1e-3, weight decay 1e-4, 30 epochs with
cosine decay to 1e-4-of-peak; plateau rule, contrast-scoped: an arm whose train
loss improves >1% over the final 3 epochs is typed UNDERTRAINED, and then ALL
arms of its contrast set rerun once at the registered second budget (60 epochs,
its own cosine; both runs published) ... Training ranks: floor((j+0.5)*N/2048),
j=0..2047 (all ranks when N<2048) ... Includes every authorized side at each
selected clock, and weights each session equally.  Each chronological session is
one optimizer minibatch; sessions and rows remain chronological in every epoch
and there is no shuffle."

REAL DATA IS NOT REACHED FROM HERE.  `--data` is refused if it lies under the
real tensor or token roots, and every tape's `opened_paths` is re-checked after
the read.  The corpus build runs in parallel; this lane is synthetic-only.
"""
from __future__ import annotations

import os
from collections import OrderedDict

# CUBLAS_WORKSPACE_CONFIG must be in the environment before the first cuBLAS
# handle is created, which happens inside torch on first CUDA use.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pathlib  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass, asdict  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import Tensor  # noqa: E402
from torch.nn import functional as F  # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms  # noqa: E402
import synth
import tapes  # noqa: E402

SEED = 20260810
PEAK_LR = 1e-3
WEIGHT_DECAY = 1e-4
COSINE_FLOOR_FRACTION = 1e-4        # "cosine decay to 1e-4-of-peak"
FIRST_BUDGET_EPOCHS = 30
SECOND_BUDGET_EPOCHS = 60
UNDERTRAINED_THRESHOLD = 0.01       # ">1% over the final 3 epochs"
RANK_COUNT = 2048                   # "floor((j+0.5)*N/2048), j=0..2047"

# §5/A1 loss weights, verbatim.
MENU_WEIGHT = 1.0 / 7.0
CERTIFICATE_WEIGHT = 0.5
PAIRWISE_WEIGHT = 0.5
OPPORTUNITY_WEIGHTS = (0.5, 0.25, 0.25)
RISK_WEIGHTS = (1.0, 0.25)
BARRIER_WEIGHT = 0.1
HUBER_DELTA = 1.0

# §1 fold walls.  gate-select is the ONLY inner-validation block (A2: "gate-select
# block sessions ONLY - 398..447/523..572, so gate-cert stays pristine; never TEST").
FOLDS = {
    "F4": {"train": (125, 395), "inner_embargo": (396, 397),
           "gate_select": (398, 447), "gate_cert": (448, 497),
           "outer_embargo": (498, 499), "test": (500, 624)},
    "F5": {"train": (125, 520), "inner_embargo": (521, 522),
           "gate_select": (523, 572), "gate_cert": (573, 622),
           "outer_embargo": (623, 624), "test": (625, 749)},
}
ADMISSIBLE_SESSIONS = (125, 749)


def fold_sessions(fold: str, block: str, available: list[int]) -> list[int]:
    low, high = FOLDS[fold][block]
    return [ordinal for ordinal in available if low <= ordinal <= high]


# --- session data ----------------------------------------------------------


#: The preassembled-session store.  MEASURED motive: an epoch's wall is
#: dominated by per-session assembly (~2.4-2.9 s x 271 = 11-13 min), not by
#: compute (0.042 s a step => ~11 s of GPU an epoch).  Assembling ONCE and
#: holding the tensors turns every epoch after the first into pure compute.
#: The budget is bytes of tensor payload; over it, the least-recently-used
#: session spills to a binary cache and is reloaded from there instead of being
#: rebuilt from the tape.  Box is 282 GB (INDEX.md), so 150 GB is the default.
CACHE_BUDGET_BYTES = int(float(os.environ.get("CAMPAIGN_CACHE_GB", "150")) * (1 << 30))
SPILL_DIR = pathlib.Path("/workspace/artifacts/cache/campaign/preassembled")


def _payload_bytes(sides: dict) -> int:
    total = 0
    for batch, targets in sides.values():
        for holder in (batch, targets):
            for name in holder.__dataclass_fields__:
                value = getattr(holder, name)
                if torch.is_tensor(value):
                    total += value.nbytes
                elif isinstance(value, tuple):
                    total += sum(item.nbytes for item in value if torch.is_tensor(item))
    return total


class SessionStore:
    """LRU over preassembled sessions, with a byte budget and a disk spill."""

    def __init__(self, budget: int = CACHE_BUDGET_BYTES) -> None:
        self.budget = budget
        self.entries: "OrderedDict[str, dict]" = OrderedDict()
        self.bytes = 0
        self.hits = 0
        self.misses = 0
        self.spills = 0
        self.spill_reads = 0

    def _spill_path(self, key: str) -> pathlib.Path:
        return SPILL_DIR / f"{key}.pt"

    def get(self, key: str, build):
        entry = self.entries.get(key)
        if entry is not None:
            self.entries.move_to_end(key)
            self.hits += 1
            return entry
        path = self._spill_path(key)
        if path.is_file():
            entry = torch.load(path, map_location="cpu", weights_only=False)
            self.spill_reads += 1
        else:
            entry = build()
            self.misses += 1
        self._insert(key, entry)
        return entry

    def _insert(self, key: str, entry: dict) -> None:
        size = _payload_bytes(entry)
        while self.entries and self.bytes + size > self.budget:
            old_key, old_entry = self.entries.popitem(last=False)
            self.bytes -= _payload_bytes(old_entry)
            path = self._spill_path(old_key)
            if not path.is_file():
                SPILL_DIR.mkdir(parents=True, exist_ok=True)
                torch.save(old_entry, path)
                self.spills += 1
        self.entries[key] = entry
        self.bytes += size

    def receipt(self) -> dict:
        return {"held_sessions": len(self.entries),
                "held_bytes": self.bytes,
                "budget_bytes": self.budget,
                "hits": self.hits, "misses": self.misses,
                "spills": self.spills, "spill_reads": self.spill_reads}


STORE = SessionStore()


#: The one-slot guard used when a session is NOT cacheable (full-row
#: evaluation passes, which happen once and would evict the training set).
_LIVE: list = []


@dataclass
class SessionData:
    """One session, loaded LAZILY.

    A real fold is 271 sessions and one session's NBBO group table alone is
    ~730 MB, so the eager list the synthetic corpus allowed is not an option on
    the real corpus.  `clocks` is read from the tiny truth `keys` leaf without
    touching a feature, and `sides` materialises on first use; the epoch loops
    call `release()` when they are done with a session."""

    ordinal: int
    clocks: Tensor        # i64 [C] the session's chronological decision ordinals
    loader: object = None  # () -> {"L"/"S": (Batch, Targets)}
    mode: str = "train"   # "train" caches the ranked rows; "full" is transient
    signature: str = ""   # what the cached assembly was built from
    corpus: str = ""      # WHICH corpus it came from -- two corpora both have
                          # an s0125, and a key without this serves one the
                          # other's tensors (caught by the XOR control)
    _sides: dict | None = None

    @property
    def sides(self) -> dict:
        if self._sides is None and self.mode == "train":
            # The ranked training rows are the SAME every epoch, so this
            # assembly is built once and then served from the store.
            key = f"{self.corpus}_s{self.ordinal:04d}_train_{self.signature}"
            object.__setattr__(self, "_sides", STORE.get(key, self.loader))
            return self._sides
        if self._sides is None:
            # AT MOST ONE session is materialised at a time.  Without this the
            # first consumer that walks the whole block -- a control's `fit`,
            # say -- pins every session it touched: measured 147 GB RSS on the
            # 271-session F4 train block before this guard existed.  Nothing in
            # the driver needs two sessions live at once (the pairwise loss uses
            # the LONG and SHORT sides of the same session).
            for other in _LIVE:
                if other is not self:
                    other.release()
            _LIVE.clear()
            builder = getattr(self, "full_loader", None) if self.mode == "full" else None
            object.__setattr__(self, "_sides", (builder or self.loader)())
            _LIVE.append(self)
        return self._sides

    def release(self) -> None:
        # A cached training assembly stays in the store; only the local handle
        # is dropped, so the next epoch is a hit rather than a rebuild.
        object.__setattr__(self, "_sides", None)
        if self in _LIVE:
            _LIVE.remove(self)


def slice_batch(batch: arms.Batch, index: Tensor) -> arms.Batch:
    """Row-slices a Batch, narrowing the session group tables to what these rows
    actually reach.

    §5 pins the raw group projection as "once per session/side/modality, not
    once per decision", and a naive row slice keeps the WHOLE session table on
    every micro-batch: measured on real session 125 that is 2.81 M NBBO groups
    re-projected 63 times per side per epoch, 0.33 s a step, ~3.8 h an epoch.
    The rows of a micro-batch are chronological and the carriers are contiguous
    (start,len) ranges, so the groups they reach are a contiguous WINDOW of the
    table: taking that window and rebasing the indices is exact -- the group
    projection is per-group elementwise -- and it is what makes the real corpus
    tractable.  Group tensors are still shared views, never copies."""
    groups, micro_slot, jsa_slot = [], [], []
    bin_seg, bin_ref, bin_segments = [], [], []
    sliced_micro = batch.micro_slot[index]
    sliced_bin_ref = batch.bin_ref[index]
    sliced_jsa = batch.jsa_slot[index]
    for modality in range(len(batch.groups)):
        slot = sliced_micro[:, modality]
        reference = sliced_bin_ref[:, modality]
        jsa_here = torch.where(batch.jsa_mod[index] == modality, sliced_jsa,
                               torch.full_like(sliced_jsa, -1))
        used_segments = reference[reference >= 0]
        used_slots = torch.cat([slot[slot >= 0].reshape(-1),
                                jsa_here[jsa_here >= 0].reshape(-1)])
        if used_segments.numel() == 0 and used_slots.numel() == 0:
            groups.append(batch.groups[modality][:1])
            micro_slot.append(torch.full_like(slot, -1))
            jsa_slot.append(torch.full_like(jsa_here, -1))
            bin_seg.append(batch.bin_seg[modality][:1])
            bin_ref.append(torch.full_like(reference, -1))
            bin_segments.append(1)
            continue
        if used_segments.numel():
            segment_low = int(used_segments.min())
            segment_high = int(used_segments.max()) + 1
            member = ((batch.bin_seg[modality] >= segment_low)
                      & (batch.bin_seg[modality] < segment_high))
            member_index = torch.nonzero(member, as_tuple=False).reshape(-1)
            low = int(member_index.min())
            high = int(member_index.max()) + 1
        else:
            segment_low, segment_high = 0, 0
            low, high = int(used_slots.min()), int(used_slots.max()) + 1
        if used_slots.numel():
            low = min(low, int(used_slots.min()))
            high = max(high, int(used_slots.max()) + 1)
        window = batch.groups[modality][low:high]
        segment = batch.bin_seg[modality][low:high]
        if segment_high > segment_low:
            rebased = segment - segment_low
            segment = torch.where((segment >= segment_low) & (segment < segment_high),
                                  rebased, torch.full_like(segment, -1))
        else:
            segment = torch.full_like(segment, -1)
        groups.append(window)
        bin_seg.append(segment)
        bin_segments.append(max(segment_high - segment_low, 1))
        bin_ref.append(torch.where(reference >= 0, reference - segment_low,
                                   torch.full_like(reference, -1)))
        micro_slot.append(torch.where(slot >= 0, slot - low, torch.full_like(slot, -1)))
        jsa_slot.append(torch.where(jsa_here >= 0, jsa_here - low,
                                    torch.full_like(jsa_here, -1)))
    merged_jsa = sliced_jsa.clone()
    for modality in range(len(batch.groups)):
        pick = batch.jsa_mod[index] == modality
        merged_jsa = torch.where(pick, jsa_slot[modality], merged_jsa)
    return arms.Batch(
        candset=batch.candset[index], candset_valid=batch.candset_valid[index],
        loc_value=batch.loc_value[index], loc_present=batch.loc_present[index],
        visible_count=batch.visible_count[index], direct=batch.direct[index],
        r_modality=batch.r_modality[index], groups=tuple(groups),
        micro_slot=torch.stack(micro_slot, dim=1), micro_phase=batch.micro_phase[index],
        micro_ckpt=batch.micro_ckpt[index], bin_ref=torch.stack(bin_ref, dim=1),
        bin_seg=tuple(bin_seg), bin_segments=tuple(bin_segments),
        jsa_mod=batch.jsa_mod[index], jsa_slot=merged_jsa,
        jsa_phase=batch.jsa_phase[index], jsa_ts_us=batch.jsa_ts_us[index],
    )


def slice_targets(targets: synth.Targets, index: Tensor) -> synth.Targets:
    return synth.Targets(**{name: getattr(targets, name)[index]
                            for name in targets.__dataclass_fields__})


def selected_ranks(count: int) -> Tensor:
    """§5/A2: floor((j+0.5)*N/2048), j=0..2047; all ranks when N < 2048."""
    if count <= 0:
        return torch.zeros(0, dtype=torch.int64)
    if count < RANK_COUNT:
        return torch.arange(count, dtype=torch.int64)
    j = torch.arange(RANK_COUNT, dtype=torch.float64)
    return torch.floor((j + 0.5) * count / RANK_COUNT).to(torch.int64)


def is_real_corpus(root: pathlib.Path) -> bool:
    """A published corpus keeps its shards under `tapes/`; the synthetic writer
    puts `s0125/` at the root."""
    return (pathlib.Path(root) / "tapes").is_dir()


def session_clocks(root: pathlib.Path, ordinal: int, real: bool) -> Tensor:
    """The session's decision ordinals, read from the truth `keys` leaf ALONE.

    This is the one place the driver needs a truth column before training, and
    it takes only that column, through the allowlist, with no feature mapped."""
    directory = (tapes._session_dir(root, ordinal, "L") if real
                 else pathlib.Path(root) / f"s{ordinal:04d}" / "L")
    tape = tapes.DecisionTape(directory)
    keys = tape.truth(["keys"], names=["keys"])["keys"]
    return torch.from_numpy(np.array(keys[:, tapes.KEY_DECISION], copy=True))


def load_sessions(root: pathlib.Path, ordinals: list[int],
                  *, verify_sha: bool = False,
                  with_groups: bool = True) -> list[SessionData]:
    root = pathlib.Path(root)
    real = is_real_corpus(root)
    if not real:
        synth.assert_synthetic_only([str(root)])
    # The corpus identity, so two roots that both publish an s0125 cannot share
    # a cache entry (and a stale spill file cannot outlive its corpus).
    corpus_key = hashlib.sha256(
        f"{root.resolve()}|groups={with_groups}".encode("utf-8")).hexdigest()[:12]
    out: list[SessionData] = []
    for ordinal in sorted(ordinals):
        clocks = session_clocks(root, ordinal, real)
        # A2 ranks pick 2048 CLOCKS, and training never looks at another row.
        # Assembling only those rows is what makes a session small enough to
        # hold for the whole fit (measured 8x fewer rows than the full tape).
        ranked = clocks[selected_ranks(int(clocks.numel()))]
        wanted = set(int(clock) for clock in ranked.tolist())
        rows_by_side, signature = {}, []
        for side in synth.SIDES:
            if real:
                ordinals_here = tapes.decision_ordinals(root, ordinal, side)
            else:
                directory = pathlib.Path(root) / f"s{ordinal:04d}" / side
                keys = tapes.DecisionTape(directory).truth(["keys"], names=["keys"])["keys"]
                ordinals_here = np.array(keys[:, tapes.KEY_DECISION], copy=True)
            picked = np.flatnonzero(np.isin(ordinals_here, list(wanted)))
            rows_by_side[side] = picked
            signature.append(str(picked.size))

        def loader(ordinal=ordinal, rows_by_side=rows_by_side):
            if real:
                return tapes.load_session(root, ordinal, verify_sha=verify_sha,
                                          with_groups=with_groups,
                                          rows_by_side=rows_by_side)
            return synth.load_session(root, ordinal, verify_sha=verify_sha)

        def full_loader(ordinal=ordinal):
            if real:
                return tapes.load_session(root, ordinal, verify_sha=verify_sha,
                                          with_groups=with_groups)
            return synth.load_session(root, ordinal, verify_sha=verify_sha)

        session = SessionData(ordinal=ordinal, clocks=clocks, loader=loader,
                              signature="x".join(signature), corpus=corpus_key)
        object.__setattr__(session, "full_loader", full_loader)
        out.append(session)
    return out


# --- A1 loss ---------------------------------------------------------------


def _weighted(loss: Tensor, weight: Tensor) -> tuple[Tensor, Tensor]:
    """Returns (sum w*l, sum w).  §5: "row losses are 1/(train rows in session),
    and each family is separately renormalized to mean weight 1" — which is
    exactly sum(w*l)/sum(w) once the family's rows are pooled."""
    return (loss * weight).sum(), weight.sum()


class LossAccumulator:
    """Accumulates each A1 family separately so the mean-weight-1 renormalisation
    is over the whole optimizer step even when it is split into micro-batches."""

    FAMILIES = (
        tuple(f"menu_{h}" for h in range(arms.N_MENU_HORIZONS))
        + ("certificate", "pairwise", "opportunity_0", "opportunity_1",
           "opportunity_2", "risk_0", "risk_1", "barrier")
    )
    WEIGHTS = dict(
        [(f"menu_{h}", MENU_WEIGHT) for h in range(arms.N_MENU_HORIZONS)]
        + [("certificate", CERTIFICATE_WEIGHT), ("pairwise", PAIRWISE_WEIGHT),
           ("opportunity_0", OPPORTUNITY_WEIGHTS[0]),
           ("opportunity_1", OPPORTUNITY_WEIGHTS[1]),
           ("opportunity_2", OPPORTUNITY_WEIGHTS[2]),
           ("risk_0", RISK_WEIGHTS[0]), ("risk_1", RISK_WEIGHTS[1]),
           ("barrier", BARRIER_WEIGHT)]
    )

    def __init__(self, denominators: dict[str, float]) -> None:
        self.denominators = denominators
        self.totals: dict[str, Tensor] = {}

    def add(self, family: str, numerator: Tensor) -> None:
        self.totals[family] = self.totals.get(family, 0.0) + numerator

    def loss(self) -> Tensor:
        total = None
        for family in self.FAMILIES:
            denominator = self.denominators.get(family, 0.0)
            if denominator <= 0 or family not in self.totals:
                continue
            piece = self.WEIGHTS[family] * self.totals[family] / denominator
            total = piece if total is None else total + piece
        return total if total is not None else torch.zeros((), dtype=torch.float32)


def family_denominators(session: SessionData, selection: "Selection") -> dict[str, float]:
    """Per-family sum of weights over the whole session (one optimizer step).

    §5: "Pair weights are 1/(train pairs in session), row losses are 1/(train
    rows in session)".  Session-balanced by construction: every session's total
    family weight is 1 before the mean-weight-1 renormalisation, and a family
    whose rows are all availability-masked away carries denominator 0 and is
    dropped rather than divided by zero.
    """
    out: dict[str, float] = {}
    row_count = selection.row_count()
    if row_count == 0:
        return out
    row_weight = 1.0 / row_count
    menu = [0.0] * arms.N_MENU_HORIZONS
    certificate = opportunity = risk = barrier = 0.0
    for side in synth.SIDES:
        index = selection.rows(side)
        if index.numel() == 0:
            continue
        targets = slice_targets(session.sides[side][1], index)
        for horizon in range(arms.N_MENU_HORIZONS):
            menu[horizon] += float(targets.menu_mask[:, horizon].sum())
        certificate += float(targets.certificate_mask.sum())
        opportunity += float(targets.row_mask.sum())
        risk += float(targets.row_mask.sum())
        barrier += float(targets.row_mask.sum())
    for horizon in range(arms.N_MENU_HORIZONS):
        out[f"menu_{horizon}"] = menu[horizon] * row_weight
    out["certificate"] = certificate * row_weight
    for which in range(3):
        out[f"opportunity_{which}"] = opportunity * row_weight
    for which in range(2):
        out[f"risk_{which}"] = risk * row_weight
    out["barrier"] = barrier * row_weight
    out["pairwise"] = 1.0 if int(selection.pair_mask.sum()) else 0.0
    return out


def accumulate_row_losses(accumulator: LossAccumulator, logits: Tensor,
                          targets: synth.Targets, row_weight: float) -> None:
    weight = torch.full((logits.shape[0],), row_weight, dtype=logits.dtype,
                        device=logits.device)
    menu_prediction = logits[:, arms.MENU_SLICE]
    for horizon in range(arms.N_MENU_HORIZONS):
        loss = F.huber_loss(menu_prediction[:, horizon], targets.menu_net[:, horizon],
                            reduction="none", delta=HUBER_DELTA)
        accumulator.add(f"menu_{horizon}",
                        _weighted(loss, weight * targets.menu_mask[:, horizon])[0])
    certificate = F.huber_loss(logits[:, arms.CERTIFICATE_INDEX], targets.certificate,
                               reduction="none", delta=HUBER_DELTA)
    accumulator.add("certificate",
                    _weighted(certificate, weight * targets.certificate_mask)[0])
    opportunity = F.binary_cross_entropy_with_logits(
        logits[:, arms.OPPORTUNITY_SLICE], targets.opportunity, reduction="none")
    for which in range(3):
        accumulator.add(f"opportunity_{which}",
                        _weighted(opportunity[:, which], weight * targets.row_mask)[0])
    risk = F.binary_cross_entropy_with_logits(
        logits[:, arms.RISK_SLICE], targets.risk, reduction="none")
    for which in range(2):
        accumulator.add(f"risk_{which}",
                        _weighted(risk[:, which], weight * targets.row_mask)[0])
    barrier = F.cross_entropy(logits[:, arms.BARRIER_SLICE], targets.barrier,
                              reduction="none")
    accumulator.add("barrier", _weighted(barrier, weight * targets.row_mask)[0])


@dataclass
class Selection:
    """The session's selected CLOCKS and, per side, the row that serves each.

    Chunking runs over CLOCKS, never rows, so §5's same-clock pair can never be
    split across two micro-batches: "The net-ranking loss contains exactly one
    pair for an equal (session,decision_ordinal) when both LONG and SHORT labels
    are OK and unequal; equal targets and missing sides are masked."
    """

    clocks: Tensor                 # i64 [K]
    row_of: dict                   # side -> i64 [K], -1 where that side is absent
    pair_mask: Tensor              # bool [K]

    def rows(self, side: str) -> Tensor:
        index = self.row_of[side]
        return index[index >= 0]

    def row_count(self) -> int:
        return sum(int(self.rows(side).numel()) for side in synth.SIDES)


def build_selection(session: SessionData, ranked: bool) -> Selection:
    """§5/A2 ranks select CLOCKS; "Includes every authorized side at each
    selected clock".  `ranked=False` scores every clock (§3: "Every row is
    predicted and retained")."""
    clocks = session.clocks
    if ranked:
        clocks = clocks[selected_ranks(int(clocks.numel()))]
    row_of = {}
    for side in synth.SIDES:
        side_clocks = session.sides[side][1].keys[:, 1]
        lookup = {int(clock): position for position, clock in enumerate(side_clocks.tolist())}
        row_of[side] = torch.tensor([lookup.get(int(clock), -1) for clock in clocks.tolist()],
                                    dtype=torch.int64)
    left, right = row_of["L"], row_of["S"]
    both = (left >= 0) & (right >= 0)
    pair_mask = torch.zeros(int(clocks.numel()), dtype=torch.bool)
    if bool(both.any()):
        long_targets = session.sides["L"][1]
        short_targets = session.sides["S"][1]
        where = torch.nonzero(both, as_tuple=False).flatten()
        long_row, short_row = left[where], right[where]
        ok = (long_targets.row_mask[long_row] > 0) & (short_targets.row_mask[short_row] > 0)
        unequal = (long_targets.menu_net[long_row, arms.H_REF_INDEX]
                   != short_targets.menu_net[short_row, arms.H_REF_INDEX])
        pair_mask[where] = ok & unequal
    return Selection(clocks=clocks, row_of=row_of, pair_mask=pair_mask)


def accumulate_pairwise(accumulator: LossAccumulator, logits: dict,
                        session: SessionData, selection: Selection,
                        window: slice, offsets: dict, pair_total: int) -> None:
    """Adds the pairs whose clock lies in `window`.  `offsets[side]` maps a clock
    position to its row inside this chunk's forward pass."""
    if pair_total == 0:
        return
    local = torch.nonzero(selection.pair_mask[window], as_tuple=False).flatten()
    if local.numel() == 0:
        return
    long_position = offsets["L"][local]
    short_position = offsets["S"][local]
    left = logits["L"][long_position, arms.H_REF_INDEX]
    right = logits["S"][short_position, arms.H_REF_INDEX]
    long_row = selection.row_of["L"][window][local]
    short_row = selection.row_of["S"][window][local]
    long_net = session.sides["L"][1].menu_net[long_row, arms.H_REF_INDEX]
    short_net = session.sides["S"][1].menu_net[short_row, arms.H_REF_INDEX]
    # Logistic on the ordered difference: the side with the larger realized
    # net_h_ref must score higher.
    sign = torch.where(long_net > short_net, 1.0, -1.0).to(left.dtype).to(left.device)
    loss = F.softplus(-sign * (left - right))
    weight = torch.full_like(loss, 1.0 / float(pair_total))
    accumulator.add("pairwise", _weighted(loss, weight)[0])


# --- the run ---------------------------------------------------------------


@dataclass
class RunConfig:
    arm: str
    fold: str
    data: str
    out: str
    epochs: int = FIRST_BUDGET_EPOCHS
    micro_batch: int = 256
    control: str = "none"
    control_options: str = ""
    device: str = "cpu"
    double_run: bool = False
    verify_sha: bool = False
    interaction_outputs: int = arms.N_OUT
    max_train_sessions: int = 0
    max_eval_sessions: int = 0


def config_hash(config: RunConfig) -> str:
    payload = json.dumps(asdict(config), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def set_determinism(device: str) -> None:
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RuntimeError("CUBLAS_WORKSPACE_CONFIG must be :4096:8 before torch starts")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(SEED)
    if device.startswith("cuda"):
        torch.cuda.manual_seed_all(SEED)


def cosine_lr(step: int, total: int) -> float:
    """Cosine from PEAK_LR down to COSINE_FLOOR_FRACTION * PEAK_LR."""
    floor = PEAK_LR * COSINE_FLOOR_FRACTION
    if total <= 1:
        return floor
    progress = min(max(step / (total - 1), 0.0), 1.0)
    return floor + 0.5 * (PEAK_LR - floor) * (1.0 + math.cos(math.pi * progress))


def run_session(model: arms.Arm, session: SessionData, config: RunConfig,
                *, ranked: bool, backward: bool, control=None,
                collect: list | None = None) -> tuple[float, int]:
    """One session = ONE optimizer step, split into clock-chunked micro-batches.

    Every chunk's loss divides by the SESSION-level family denominators, so the
    chunk losses sum to the exact unchunked session loss and gradient
    accumulation is exact rather than approximate.
    """
    selection = build_selection(session, ranked=ranked)
    denominators = family_denominators(session, selection)
    if not denominators:
        return 0.0, 0
    row_weight = 1.0 / selection.row_count()
    pair_total = int(selection.pair_mask.sum())
    clock_count = int(selection.clocks.numel())
    step = max(1, config.micro_batch // len(synth.SIDES))
    device = torch.device(config.device)
    total, tokens = 0.0, 0
    for lo in range(0, clock_count, step):
        hi = min(lo + step, clock_count)
        window = slice(lo, hi)
        accumulator = LossAccumulator(denominators)
        logits: dict[str, Tensor] = {}
        offsets: dict[str, Tensor] = {}
        for side in synth.SIDES:
            index = selection.row_of[side][window]
            present = index >= 0
            offsets[side] = torch.cumsum(present.to(torch.int64), 0) - 1
            rows = index[present]
            if rows.numel() == 0:
                logits[side] = torch.zeros(0, arms.N_OUT, device=device)
                continue
            batch, targets = session.sides[side]
            sub_batch = slice_batch(batch, rows).to(device)
            sub_targets = slice_targets(targets, rows).to(device)
            if control is not None:
                sub_batch, sub_targets = control(sub_batch, sub_targets, session, side)
            scored = model(sub_batch)
            logits[side] = scored
            accumulate_row_losses(accumulator, scored, sub_targets, row_weight)
            tokens += scored.shape[0] * (
                3 * arms.MICRO_LENGTH + 3 * arms.BIN_LENGTH + arms.JSA_TOKENS)
            if collect is not None:
                collect.append((scored.detach().cpu().numpy(),
                                sub_targets.keys.detach().cpu().numpy()))
        accumulate_pairwise(accumulator, logits, session, selection, window, offsets,
                            pair_total)
        loss = accumulator.loss()
        if backward and loss.requires_grad:
            loss.backward()
        total += float(loss.detach())
    return total, tokens


def heartbeat(message: str) -> None:
    """One line to stderr — `lab/run.sh` records stderr as the run's heartbeat,
    and a long fit with no heartbeat is indistinguishable from a hung one."""
    print(message, file=sys.stderr, flush=True)


def run_epoch(model: arms.Arm, sessions: list[SessionData], config: RunConfig,
              optimizer, learning_rate: float | None,
              control=None) -> tuple[float, int]:
    """One chronological pass.  §5: "Each chronological session is one optimizer
    minibatch; sessions and rows remain chronological in every epoch and there is
    no shuffle." """
    model.train(True)
    total, tokens = 0.0, 0
    started = time.time()
    for position, session in enumerate(sessions, start=1):
        optimizer.zero_grad(set_to_none=True)
        for group in optimizer.param_groups:
            group["lr"] = learning_rate
        loss, session_tokens = run_session(model, session, config, ranked=True,
                                           backward=True, control=control)
        optimizer.step()
        session.release()
        elapsed = time.time() - started
        heartbeat(f"train s{session.ordinal} {position}/{len(sessions)} "
                  f"{elapsed / position:.1f}s/session "
                  f"eta {(len(sessions) - position) * elapsed / position / 60:.1f}m")
        total += loss
        tokens += session_tokens
    return total, tokens


@torch.no_grad()
def evaluate(model: arms.Arm, sessions: list[SessionData], config: RunConfig,
             control=None) -> tuple[np.ndarray, np.ndarray, float]:
    """Scores every row of every session (§3: "Every row is predicted and
    retained") and returns (logits, keys, mean session loss)."""
    model.eval()
    collected: list = []
    total, steps = 0.0, 0
    for session in sessions:
        session.release()
        object.__setattr__(session, "mode", "full")
        loss, _ = run_session(model, session, config, ranked=False, backward=False,
                              control=control, collect=collected)
        object.__setattr__(session, "mode", "train")
        total += loss
        steps += 1
        session.release()
        if steps % 10 == 0:
            heartbeat(f"eval {steps}/{len(sessions)} sessions")
    if not collected:
        return (np.zeros((0, arms.N_OUT), dtype=np.float32),
                np.zeros((0, 4), dtype=np.int64), 0.0)
    logits = np.concatenate([piece[0] for piece in collected])
    keys = np.concatenate([piece[1] for piece in collected])
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    return logits[order], keys[order], total / max(steps, 1)


class UtilisationSampler:
    """Samples GPU utilisation DURING the run, not after it.

    C7 wants a GPU receipt.  `torch.cuda.utilization()` needs pynvml, which this
    box does not have and which this lane may not install, so the fallback shells
    out to nvidia-smi on a background thread.  Reading utilisation after training
    would report an idle device, which is why the sampler runs alongside.
    """

    INTERVAL_SECONDS = 0.25

    def __init__(self, device: str) -> None:
        self.enabled = device.startswith("cuda") and torch.cuda.is_available()
        self.samples: list[int] = []
        self.method = "DISABLED"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _read(self) -> int | None:
        try:
            return int(torch.cuda.utilization())
        except Exception:  # noqa: BLE001 — no pynvml on this box
            pass
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5)
            if out.returncode == 0 and out.stdout.strip():
                return int(out.stdout.strip().splitlines()[0])
        except Exception:  # noqa: BLE001 — no nvidia-smi either
            pass
        return None

    def _loop(self) -> None:
        while not self._stop.wait(self.INTERVAL_SECONDS):
            reading = self._read()
            if reading is not None:
                self.samples.append(reading)

    def __enter__(self) -> "UtilisationSampler":
        if not self.enabled:
            return self
        first = self._read()
        if first is None:
            self.method = "UNAVAILABLE_NO_NVML_NO_NVIDIA_SMI"
            return self
        self.method = "nvidia-smi/torch"
        self.samples.append(first)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def report(self) -> dict:
        if not self.enabled:
            return {"utilization_percent_mean": None, "utilization_percent_max": None,
                    "utilization_samples": 0, "utilization_method": "DISABLED"}
        if not self.samples:
            return {"utilization_percent_mean": self.method,
                    "utilization_percent_max": self.method,
                    "utilization_samples": 0, "utilization_method": self.method}
        return {
            "utilization_percent_mean": round(sum(self.samples) / len(self.samples), 1),
            "utilization_percent_max": max(self.samples),
            "utilization_samples": len(self.samples),
            "utilization_method": self.method,
        }


def gpu_receipt(device: str, wall: float, tokens: int,
                sampler: UtilisationSampler | None = None) -> dict:
    receipt = {
        "device": device,
        "wall_seconds": round(wall, 4),
        "model_tokens": tokens,
        "tokens_per_second": round(tokens / wall, 2) if wall > 0 else 0.0,
        "tokens_formula": "rows * (3*128 micro + 3*120 bin + 192 jsa)",
        "vram_peak_bytes": 0,
    }
    if device.startswith("cuda") and torch.cuda.is_available():
        receipt["vram_peak_bytes"] = int(torch.cuda.max_memory_allocated())
    receipt.update(sampler.report() if sampler is not None
                   else UtilisationSampler(device).report())
    return receipt


def available_sessions(root: pathlib.Path) -> list[int]:
    """The published session ordinals under `root`.  §1: "Only sessions 125..749
    are admissible" and "Any path/session >=750 ... is refused before payload
    resolution" — so the refusal happens here, before any tape is opened."""
    root = pathlib.Path(root)
    base = root / "tapes" if is_real_corpus(root) else root
    if base is root:
        synth.assert_synthetic_only([str(root)])
    found = sorted(int(path.name[1:]) for path in base.glob("s[0-9]*")
                   if (path / "L" / "manifest.tsv").is_file())
    outside = [o for o in found
               if not ADMISSIBLE_SESSIONS[0] <= o <= ADMISSIBLE_SESSIONS[1]]
    if outside:
        raise RuntimeError(f"§1 refuses sessions outside 125..749: {outside}")
    return found


def train_once(config: RunConfig, control=None) -> dict:
    set_determinism(config.device)
    available = available_sessions(pathlib.Path(config.data))
    train_ordinals = fold_sessions(config.fold, "train", available)
    if config.max_train_sessions:
        train_ordinals = train_ordinals[-config.max_train_sessions:]
    with_groups = config.arm in arms.NATIVE_ARMS
    train_sessions = load_sessions(pathlib.Path(config.data), train_ordinals,
                                   verify_sha=config.verify_sha,
                                   with_groups=with_groups)
    inner_ordinals = fold_sessions(config.fold, "gate_select", available)
    if config.max_eval_sessions:
        inner_ordinals = inner_ordinals[:config.max_eval_sessions]
    inner_sessions = load_sessions(pathlib.Path(config.data), inner_ordinals,
                                   verify_sha=config.verify_sha,
                                   with_groups=with_groups)
    if not train_sessions:
        raise RuntimeError(f"fold {config.fold} has no TRAIN session under {config.data}")

    model = arms.build_arm(config.arm, interaction_outputs=config.interaction_outputs)
    arms.assert_frozen_capacities()
    model = model.to(torch.device(config.device))
    # §7 controls are flag variants of THIS script; a control that needs the
    # TRAIN-only normalisation fits it on TRAIN and nothing else.
    if control is not None and hasattr(control, "fit"):
        control.fit(train_sessions)
    if control is not None and hasattr(control, "bind"):
        control.bind(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=PEAK_LR,
                                  weight_decay=WEIGHT_DECAY)

    train_curve, inner_curve = [], []
    started = time.time()
    tokens = 0
    if config.device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    with UtilisationSampler(config.device) as sampler:
        for epoch in range(config.epochs):
            learning_rate = cosine_lr(epoch, config.epochs)
            loss, epoch_tokens = run_epoch(model, train_sessions, config, optimizer,
                                           learning_rate, control)
            tokens += epoch_tokens
            train_curve.append(loss / max(len(train_sessions), 1))
            if inner_sessions:
                _, _, inner = evaluate(model, inner_sessions, config, control)
                inner_curve.append(inner)
    wall = time.time() - started

    logits, keys, _ = evaluate(model, train_sessions + inner_sessions, config, control)
    undertrained = False
    if len(train_curve) >= 4 and abs(train_curve[-4]) > 0:
        improvement = (train_curve[-4] - train_curve[-1]) / abs(train_curve[-4])
        undertrained = bool(improvement > UNDERTRAINED_THRESHOLD)
    return {
        "config": asdict(config),
        "config_sha256": config_hash(config),
        "train_curve": train_curve,
        "inner_val_curve": inner_curve,
        "undertrained": undertrained,
        "undertrained_rule": ">1% train-loss improvement over the final 3 epochs",
        "second_budget_epochs": SECOND_BUDGET_EPOCHS,
        "capacity": [
            {"module": row[0], "built": row[1], "frozen": row[2], "agrees": row[3]}
            for row in arms.frozen_capacity_report()
        ],
        "gpu_receipt": gpu_receipt(config.device, wall, tokens, sampler),
        "logits": logits,
        "keys": keys,
        "train_sessions": [s.ordinal for s in train_sessions],
        "inner_val_sessions": [s.ordinal for s in inner_sessions],
    }


def train(config: RunConfig, control=None) -> dict:
    first = train_once(config, control)
    determinism = None
    if config.double_run:
        second = train_once(config, control)
        determinism = bool(np.array_equal(first["logits"], second["logits"]))
    first["determinism_bit_identical"] = determinism
    return first


def publish(result: dict, out: pathlib.Path) -> pathlib.Path:
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "logits.npy", result["logits"])
    np.save(out / "keys.npy", result["keys"])
    receipt = {name: value for name, value in result.items()
               if name not in ("logits", "keys")}
    receipt["logits_shape"] = list(result["logits"].shape)
    receipt["key_columns"] = ["session_ordinal", "decision_ordinal", "side_index",
                              "decision_ts_ns"]
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n",
                                      encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", required=True, choices=list(arms.ARM_NAMES))
    parser.add_argument("--fold", required=True, choices=list(FOLDS))
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--epochs", type=int, default=FIRST_BUDGET_EPOCHS)
    parser.add_argument("--micro-batch", type=int, default=256)
    parser.add_argument("--control", default="none")
    parser.add_argument("--control-options", default="")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--double-run", action="store_true")
    parser.add_argument("--verify-sha", action="store_true")
    parser.add_argument("--max-eval-sessions", type=int, default=0,
                        help="cap the gate-select block the same way (0 = all 50)")
    parser.add_argument("--max-train-sessions", type=int, default=0,
                        help="cap the TRAIN block at the most recent N sessions "
                             "(0 = the whole block).  A real fold is I/O bound at "
                             "~9s per session per epoch, so a control that must "
                             "fit a wall-clock budget states its cap explicitly "
                             "and carries it in the receipt.")
    args = parser.parse_args(argv)

    import controls   # local import: controls imports train for its flag table

    config = RunConfig(arm=args.arm, fold=args.fold, data=args.data, out=args.out,
                       epochs=args.epochs, micro_batch=args.micro_batch,
                       control=args.control, control_options=args.control_options,
                       device=args.device, double_run=args.double_run,
                       verify_sha=args.verify_sha,
                       max_train_sessions=args.max_train_sessions,
                       max_eval_sessions=args.max_eval_sessions)
    result = train(config, controls.build(config.control, config.control_options))
    publish(result, pathlib.Path(config.out))
    print(json.dumps({
        "arm": config.arm, "fold": config.fold, "control": config.control,
        "max_train_sessions": config.max_train_sessions,
        "max_eval_sessions": config.max_eval_sessions,
        "config_sha256": result["config_sha256"],
        "final_train_loss": result["train_curve"][-1] if result["train_curve"] else None,
        "final_inner_val_loss": (result["inner_val_curve"][-1]
                                 if result["inner_val_curve"] else None),
        "undertrained": result["undertrained"],
        "determinism_bit_identical": result["determinism_bit_identical"],
        "gpu_receipt": result["gpu_receipt"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
