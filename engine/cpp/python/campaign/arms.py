"""arms.py — the frozen TASK CARD V4 §5 model ladder, exactly as the card spells it.

SPEC (verbatim law): evidence/claims/native_state/TASK_CARD_V4_DRAFT.md §5,
card sha256 5c26438b12dd90e15b005375829d976fa46a1710c78041ff20ffc587dc092792.

Everything here is dictated by §5; nothing is chosen.  Where §5 fixes a number
it appears as a module-level constant, and `assert_frozen_capacities()` proves
the built modules carry exactly the nine parameter counts §5's algebra pins:

    direct encoder                          20,224
    stock-print micro carrier               38,176
    stock-NBBO  micro carrier               38,048
    option-print micro carrier              38,816
    120-bin carrier                         38,336
    native stock-print encoder              96,736
    native stock-NBBO  encoder              96,608
    native option-print encoder             97,376
    DIRECT_CAPACITY_MATCH, per modality    101,120

THE BIAS LAW (§5, verbatim): "both candidate-element MLP layers and the location
projection use biases; raw value projections, direct residual encoders, TCN
convolutions, role projections, and interaction projections are bias-free.  The
stock-print, NBBO, and option output heads are bias-free so an absent zero
embedding contributes exactly zero; the state head uses biases in both layers."
That last sentence is a testable law, not a comment: `test_campaign.py` feeds a
zero modality embedding and requires the head contribution to be bitwise zero.

SHARING.  §5 calls the 2x64 phase table "the shared bias-free two-state phase
table" and JSA reuses "the SAME shared 64d base group embedding" and "the shared
2x64 phase embedding".  So the table and the three base group projections are
ONE object each, referenced by the three micro carriers and by JSA.  §5's
per-carrier algebra nevertheless charges the 128 phase parameters to EVERY micro
carrier (69*32+32*64+128+... = 38,176).  Both facts are the card's; this module
honours both by sharing the object and by having `declared_parameter_count()`
return the card's per-carrier accounting.  `unique_parameter_count()` reports the
physically distinct total for the same modules.  RULED CONFIRMED (CC-009 note,
2026-08-11): shared object + per-carrier accounting is the intended reading.

N_out.  §5/A1: "N_out recomputed and pinned at freeze".  The card's own output
list is menu regressions for the seven horizons (7) + certificate (1) +
opportunity BCEs (3) + risk BCEs (2) + barrier three-class (3) = 16.  That is
arithmetic on the frozen list, not a choice -- and it is now RULED and pinned in
the card as N_out = 16 (2026-08-11).

RULINGS carried by this module (card, 2026-08-11): CC-009 pins W = N_out x 8 and
confirms the shared phase-table object with the card's per-carrier accounting;
the TCN block order is depthwise -> pointwise -> SiLU -> residual; and JSA sits
on the NATIVE_ORDER additive base, so JSA and JSA_CAPACITY_MATCH share an
identical base and differ only by the 16 lambda scalars.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import torch
from torch import Tensor, nn
from torch.nn import functional as F

# --- frozen §5 numbers -----------------------------------------------------

D_MODEL = 64
CANDSET_FIELDS = 24
LOCATION_VALUES = 16          # §5: "The exact 16 location/clock values"
LOCATION_INPUTS = 2 * LOCATION_VALUES  # values + parallel presence bits = 32
DIRECT_COLUMNS = 60           # §4: "Exactly 60 columns/modality"
MICRO_LENGTH = 128            # §4/§5: "the most recent 128 groups"
BIN_LENGTH = 120              # §4/§5: "exactly 120 complete ... one-second bins"
MICRO_DILATIONS = (1, 2, 4, 8)
BIN_DILATIONS = (1, 2, 4, 8, 16, 32, 64)
TCN_KERNEL = 3
MICRO_ROLE_INPUTS = 4 * D_MODEL + 4       # §5: "bias-free 260->64"
BIN_REDUCER_INPUTS = 2 * D_MODEL + 2      # §5: "projected 130->64"
CHECKPOINT_OFFSETS_S = (60, 30, 15, 5, 1, 0)
PHASE_STATES = 2              # approach / response; EQUAL contributes zero
INTERACTION_RANK = 8
JSA_TOKENS = 192              # §5 5b: "M=192 merged tokens"
JSA_BLOCKS = 4
JSA_HEADS = 4
JSA_FFN = 128
DIRECT_CAPACITY_MATCH_ENCODERS = 5
MODALITIES = ("stock_print", "stock_nbbo", "option_print")
GROUP_INPUTS = {"stock_print": 69, "stock_nbbo": 65, "option_print": 89}
GROUP_HIDDEN = 32
CANDSET_HIDDEN = 32
HEAD_HIDDEN = 32

# A1 output vector, in this fixed order.  train.py's loss reads these slices.
N_MENU_HORIZONS = 7
MENU_SLICE = slice(0, 7)
CERTIFICATE_INDEX = 7
OPPORTUNITY_SLICE = slice(8, 11)
RISK_SLICE = slice(11, 13)
BARRIER_SLICE = slice(13, 16)
N_OUT = 16
# The seven menu horizons are {2,5,15,30,60,120 min, close}; the card's h-LAW
# fixes the comparability horizon h_ref = 15 min, and the auxiliary risk head
# binds to 60 min.
H_REF_INDEX = 2
H_60M_INDEX = 4
NET_SCALE = 30000.0           # A1: "net_h/30000", the $300 wall in net cents

FROZEN_CAPACITY = {
    "direct_encoder": 20224,
    "micro_stock_print": 38176,
    "micro_stock_nbbo": 38048,
    "micro_option_print": 38816,
    "bin_carrier": 38336,
    "native_encoder_stock_print": 96736,
    "native_encoder_stock_nbbo": 96608,
    "native_encoder_option_print": 97376,
    "direct_capacity_match_per_modality": 101120,
}

ARM_NAMES = (
    "CLOCK_STATE",
    "DIRECT_RAW",
    "DIRECT_CAPACITY_MATCH",
    "NATIVE_ORDER",
    "NATIVE_INTERACTION",
    "JOINT_STREAM_ATTENTION",
    "JSA_CAPACITY_MATCH",
    "DYNAMIC_POLICY",
)
# §6: DYNAMIC_POLICY has "no new fit/parameters: the NATIVE_INTERACTION scores
# are replayed through the watch chronology".  It is therefore the same fitted
# object; only the replay differs, which lives in the replay stage, not here.
REPLAY_ONLY_ARMS = {"DYNAMIC_POLICY": "NATIVE_INTERACTION"}
CERTIFIED_CONTRASTS = {
    "rung": ("CLOCK_STATE", "DIRECT_RAW", "DIRECT_CAPACITY_MATCH",
             "NATIVE_ORDER", "NATIVE_INTERACTION"),
    "jsa": ("JOINT_STREAM_ATTENTION", "JSA_CAPACITY_MATCH"),
}


# --- the batch contract ----------------------------------------------------


@dataclass
class Batch:
    """Exactly the tensors §5 needs for one micro-batch of action rows.

    Group tensors are SESSION-level: §5 pins "Shared raw group projection costs
    G_s*(input*32+32*64) once per session/side/modality, not once per decision",
    so the base group embedding is computed once over the session's groups and
    the per-row carriers gather into it.  Every gather index uses -1 for pad and
    every gathered pad position contributes exactly zero.

    Shapes (B rows, G_m groups of modality m, S = max groups in any 1s bin):
      candset        f32 [B, C, 24]        C = visible-candidate capacity
      candset_valid  f32 [B, C]
      loc_value      f32 [B, 16]
      loc_present    f32 [B, 16]
      visible_count  f32 [B]               r_state = min(1, count/4)
      direct         f32 [B, 3, 60]
      r_modality     f32 [B, 3]            the frozen r_modality DIRECT column
      groups         3 x f32 [G_m, 69|65|89]
      micro_slot     i64 [B, 3, 128]       index into groups[m]; -1 = left pad
      micro_phase    i64 [B, 3, 128]       0 APPROACH, 1 RESPONSE, 2 EQUAL
      micro_ckpt     i64 [B, 3, 6]         position in 0..127; -1 = unavailable
      bin_slot       i64 [B, 3, 120, S]    index into groups[m]; -1 = empty
      jsa_mod        i64 [B, 192]          modality of the merged token; -1 pad
      jsa_slot       i64 [B, 192]          index into groups[jsa_mod]
      jsa_phase      i64 [B, 192]
      jsa_ts_us      i64 [B, 192]          token timestamp in microseconds
    """

    candset: Tensor
    candset_valid: Tensor
    loc_value: Tensor
    loc_present: Tensor
    visible_count: Tensor
    direct: Tensor
    r_modality: Tensor
    groups: tuple[Tensor, Tensor, Tensor]
    micro_slot: Tensor
    micro_phase: Tensor
    micro_ckpt: Tensor
    bin_slot: Tensor
    jsa_mod: Tensor
    jsa_slot: Tensor
    jsa_phase: Tensor
    jsa_ts_us: Tensor

    @property
    def rows(self) -> int:
        return int(self.candset.shape[0])

    def to(self, device: torch.device) -> "Batch":
        def move(value):
            if isinstance(value, torch.Tensor):
                return value.to(device)
            if isinstance(value, tuple):
                return tuple(move(item) for item in value)
            return value

        return Batch(**{name: move(getattr(self, name)) for name in self.__dataclass_fields__})


# --- masked reductions (the §4 "divide only by present members" law) --------


def masked_mean(values: Tensor, mask: Tensor, dim: int) -> Tensor:
    """Mean over present members; zero present members emits exactly 0."""
    total = (values * mask).sum(dim)
    count = mask.sum(dim).clamp_min(1.0)
    return total / count


def masked_max(values: Tensor, mask: Tensor, dim: int) -> Tensor:
    """Max over present members; zero present members emits exactly 0."""
    floor = torch.finfo(values.dtype).min
    picked = torch.where(mask > 0, values, torch.full_like(values, floor)).max(dim).values
    any_present = mask.sum(dim) > 0
    return torch.where(any_present, picked, torch.zeros_like(picked))


def _gather_rows(table: Tensor, index: Tensor) -> tuple[Tensor, Tensor]:
    """table[index] with -1 mapped to an appended zero row; also returns validity."""
    zero = table.new_zeros((1,) + tuple(table.shape[1:]))
    padded = torch.cat([table, zero], dim=0)
    valid = (index >= 0).to(table.dtype)
    safe = torch.where(index >= 0, index, torch.full_like(index, table.shape[0]))
    return padded[safe.reshape(-1)].reshape(tuple(index.shape) + tuple(table.shape[1:])), valid


# --- primitives ------------------------------------------------------------


class PhaseTable(nn.Module):
    """§5: "the shared bias-free two-state phase table has 128 parameters".

    Three phase codes are addressed: 0 APPROACH, 1 RESPONSE, 2
    PHASE_EQUAL_UNORDERED.  §4: visibility-equal groups "receive no phase
    embedding", so code 2 resolves to an exact zero row that carries no
    parameter.
    """

    def __init__(self) -> None:
        super().__init__()
        # §5 pins the table's SHAPE and that it is bias-free; it does not pin an
        # initialiser, so this uses torch's own embedding default, N(0,1).  A
        # zero init would silently make §7 (n)'s ablation a no-op at step 0.
        self.table = nn.Parameter(torch.empty(PHASE_STATES, D_MODEL).normal_())

    def forward(self, phase: Tensor) -> Tensor:
        rows = torch.cat([self.table, self.table.new_zeros(1, D_MODEL)], dim=0)
        return rows[phase.clamp(min=0, max=PHASE_STATES).reshape(-1)].reshape(
            tuple(phase.shape) + (D_MODEL,)
        )


class GroupProjection(nn.Module):
    """§5: bias-free base group projection 69->32->64 (or 65/89)."""

    def __init__(self, inputs: int) -> None:
        super().__init__()
        self.first = nn.Linear(inputs, GROUP_HIDDEN, bias=False)
        self.second = nn.Linear(GROUP_HIDDEN, D_MODEL, bias=False)

    def forward(self, raw: Tensor) -> Tensor:
        return self.second(F.silu(self.first(raw)))

    def declared_parameter_count(self) -> int:
        return self.first.weight.numel() + self.second.weight.numel()


class CausalTCNBlock(nn.Module):
    """§5: "bias-free depthwise conv (64*3 parameters) plus bias-free 64x64
    pointwise, SiLU, no dropout", residual, causal, kernel 3.

    Left pad is exact zero (§5: "Left pad is exact zero with a separate validity
    mask and stays zero"): the pad is applied on the left only, so no position
    can see its own future.
    """

    def __init__(self, dilation: int) -> None:
        super().__init__()
        self.dilation = dilation
        self.depthwise = nn.Conv1d(D_MODEL, D_MODEL, TCN_KERNEL, groups=D_MODEL,
                                   dilation=dilation, bias=False)
        self.pointwise = nn.Conv1d(D_MODEL, D_MODEL, 1, bias=False)

    def forward(self, sequence: Tensor) -> Tensor:
        padded = F.pad(sequence, (self.dilation * (TCN_KERNEL - 1), 0))
        return sequence + F.silu(self.pointwise(self.depthwise(padded)))

    def declared_parameter_count(self) -> int:
        return self.depthwise.weight.numel() + self.pointwise.weight.numel()


class DirectEncoder(nn.Module):
    """§5: "Each direct encoder is bias-free 60->64 plus four bias-free 64x64
    residual SiLU blocks."  20,224 parameters."""

    def __init__(self) -> None:
        super().__init__()
        self.project = nn.Linear(DIRECT_COLUMNS, D_MODEL, bias=False)
        self.blocks = nn.ModuleList(
            [nn.Linear(D_MODEL, D_MODEL, bias=False) for _ in range(4)]
        )

    def forward(self, summaries: Tensor) -> Tensor:
        state = self.project(summaries)
        for block in self.blocks:
            state = state + F.silu(block(state))
        return state

    def declared_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())


class MicroCarrier(nn.Module):
    """§5: the 128-group micro carrier.

    "four residual causal TCN blocks, width 64, kernel 3, dilations 1/2/4/8.
     Its role vector is approach, current, current-approach, and mean of valid
     latent checkpoints at cutoff-{60,30,15,5,1,0}s plus four presence bits:
     bias-free 260->64, yielding h_micro."

    Declared capacity charges the shared phase table's 128 parameters to this
    carrier, exactly as §5's arithmetic does.
    """

    def __init__(self, projection: GroupProjection, phase: PhaseTable) -> None:
        super().__init__()
        self._projection = (projection,)   # tuple => shared, not re-registered
        self._phase = (phase,)
        self.blocks = nn.ModuleList([CausalTCNBlock(d) for d in MICRO_DILATIONS])
        self.role = nn.Linear(MICRO_ROLE_INPUTS, D_MODEL, bias=False)

    def forward(self, group_embedding: Tensor, slot: Tensor, phase: Tensor,
                checkpoint: Tensor) -> Tensor:
        gathered, valid = _gather_rows(group_embedding, slot)      # [B,128,64], [B,128]
        tokens = (gathered + self._phase[0](phase)) * valid.unsqueeze(-1)
        latent = tokens.transpose(1, 2)
        for block in self.blocks:
            latent = block(latent)
        latent = latent.transpose(1, 2) * valid.unsqueeze(-1)      # pad stays zero

        approach_mask = ((phase == 0) & (slot >= 0)).to(latent.dtype)
        approach = masked_mean(latent, approach_mask.unsqueeze(-1), dim=1)
        approach_present = (approach_mask.sum(1) > 0).to(latent.dtype)

        # "current" = the latent of the most recent valid group.
        positions = torch.arange(latent.shape[1], device=latent.device).expand(latent.shape[:2])
        newest = torch.where(valid > 0, positions, torch.full_like(positions, -1)).max(1).values
        current_present = (newest >= 0).to(latent.dtype)
        current = latent.gather(
            1, newest.clamp_min(0).view(-1, 1, 1).expand(-1, 1, D_MODEL)
        ).squeeze(1) * current_present.unsqueeze(-1)

        difference_present = approach_present * current_present
        difference = (current - approach) * difference_present.unsqueeze(-1)

        checkpoint_valid = (checkpoint >= 0).to(latent.dtype)
        picked = latent.gather(
            1, checkpoint.clamp_min(0).unsqueeze(-1).expand(-1, -1, D_MODEL)
        )
        checkpoints = masked_mean(picked, checkpoint_valid.unsqueeze(-1), dim=1)
        checkpoint_present = (checkpoint_valid.sum(1) > 0).to(latent.dtype)

        role = torch.cat(
            [
                approach, current, difference, checkpoints,
                torch.stack([approach_present, current_present, difference_present,
                             checkpoint_present], dim=1),
            ],
            dim=1,
        )
        return self.role(role)

    def declared_parameter_count(self) -> int:
        own = self.role.weight.numel() + sum(b.declared_parameter_count() for b in self.blocks)
        return (self._projection[0].declared_parameter_count()
                + self._phase[0].table.numel()
                + own)


class BinCarrier(nn.Module):
    """§5: the 120-bin carrier.

    "the bias-free 130->64 reducer above followed by seven width64/kernel3
     residual causal blocks with dilations 1/2/4/8/16/32/64 (receptive field
     255); its final position is h_bin."

    §4 fixes the reduction inside a bin: "the 64d equal-time group embeddings are
    reduced by mean+max plus log group count/nonempty, then projected 130->64".
    """

    def __init__(self) -> None:
        super().__init__()
        self.reduce = nn.Linear(BIN_REDUCER_INPUTS, D_MODEL, bias=False)
        self.blocks = nn.ModuleList([CausalTCNBlock(d) for d in BIN_DILATIONS])

    def forward(self, group_embedding: Tensor, slot: Tensor) -> Tensor:
        gathered, valid = _gather_rows(group_embedding, slot)      # [B,120,S,64]
        mask = valid.unsqueeze(-1)
        mean = masked_mean(gathered, mask, dim=2)
        maximum = masked_max(gathered, mask, dim=2)
        count = valid.sum(2)
        reduced = self.reduce(
            torch.cat([mean, maximum, torch.log1p(count).unsqueeze(-1),
                       (count > 0).to(gathered.dtype).unsqueeze(-1)], dim=-1)
        )
        latent = reduced.transpose(1, 2)
        for block in self.blocks:
            latent = block(latent)
        return latent[:, :, -1]

    def declared_parameter_count(self) -> int:
        return self.reduce.weight.numel() + sum(
            block.declared_parameter_count() for block in self.blocks
        )


class CandidateSetEncoder(nn.Module):
    """§5: "Shared element MLP 24->32->32 (SiLU); set mean+max gives 64." Biased."""

    def __init__(self) -> None:
        super().__init__()
        self.first = nn.Linear(CANDSET_FIELDS, CANDSET_HIDDEN, bias=True)
        self.second = nn.Linear(CANDSET_HIDDEN, CANDSET_HIDDEN, bias=True)

    def forward(self, candidates: Tensor, valid: Tensor) -> Tensor:
        element = self.second(F.silu(self.first(candidates)))
        mask = valid.unsqueeze(-1)
        element = element * mask
        return torch.cat([masked_mean(element, mask, 1), masked_max(element, mask, 1)], dim=1)


class LocationBlock(nn.Module):
    """§5: "The 32 values/bits project 32->64 and add to the 64d candidate-set
    embedding."  Biased."""

    def __init__(self) -> None:
        super().__init__()
        self.project = nn.Linear(LOCATION_INPUTS, D_MODEL, bias=True)

    def forward(self, value: Tensor, present: Tensor) -> Tensor:
        return self.project(torch.cat([value * present, present], dim=1))


class StateEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.candidates = CandidateSetEncoder()
        self.location = LocationBlock()

    def forward(self, batch: Batch) -> Tensor:
        return (self.candidates(batch.candset, batch.candset_valid)
                + self.location(batch.loc_value, batch.loc_present))


class Head(nn.Module):
    """§5: "separate stock-print, stock-NBBO, option-print, and state heads
    64->32->N_out (SiLU); logits add."  Market heads bias-free (so an absent zero
    embedding contributes exactly zero); the state head uses biases in both."""

    def __init__(self, bias: bool) -> None:
        super().__init__()
        self.first = nn.Linear(D_MODEL, HEAD_HIDDEN, bias=bias)
        self.second = nn.Linear(HEAD_HIDDEN, N_OUT, bias=bias)

    def forward(self, embedding: Tensor) -> Tensor:
        return self.second(F.silu(self.first(embedding)))


class NativeInteraction(nn.Module):
    """§5 rung 5: "identical additive logits plus rank-8 residual
    2*tanh(W[(Us h_stock)*(Uo h_option)*(Ue h_state)*g])", with Us/Uo/Ue
    bias-free 8x64 and W bias-free, "(eight outputs by rank)".

    RULED (CC-009 in the card, 2026-08-11): W is N_out x rank.  §5 spells it
    "8x8", which was N_out x rank back when V3.3.3's N_out was 8; A1 recomputes
    N_out, and a residual added to the additive logits must have N_out outputs.
    `interaction_outputs` keeps the literal-8 reading reachable for an ablation
    but the campaign default is N_OUT and no other rung is affected.
    """

    def __init__(self, interaction_outputs: int = N_OUT) -> None:
        super().__init__()
        self.stock = nn.Linear(D_MODEL, INTERACTION_RANK, bias=False)
        self.option = nn.Linear(D_MODEL, INTERACTION_RANK, bias=False)
        self.state = nn.Linear(D_MODEL, INTERACTION_RANK, bias=False)
        self.combine = nn.Linear(INTERACTION_RANK, interaction_outputs, bias=False)
        self.outputs = interaction_outputs

    def forward(self, stock: Tensor, option: Tensor, state: Tensor, gate: Tensor) -> Tensor:
        rank = self.stock(stock) * self.option(option) * self.state(state) * gate.unsqueeze(-1)
        residual = 2.0 * torch.tanh(self.combine(rank))
        if self.outputs == N_OUT:
            return residual
        padded = residual.new_zeros(residual.shape[0], N_OUT)
        padded[:, : self.outputs] = residual
        return padded


# --- JSA (§5 5b) -----------------------------------------------------------


class JSAAttention(nn.Module):
    """Time-in-attention-bias self attention, bias-free, 4 heads, d=64.

    §5 5b: "per head h, b_h(i,j) = -softplus(lambda_h)*log1p(dt_us(i,j)) for
    t_j <= t_i; equal timestamps are mutually unmasked with dt=0".
    """

    def __init__(self) -> None:
        super().__init__()
        self.query = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.key = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.value = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.out = nn.Linear(D_MODEL, D_MODEL, bias=False)
        self.decay = nn.Parameter(torch.zeros(JSA_HEADS))

    def forward(self, tokens: Tensor, valid: Tensor, log_delta: Tensor,
                causal: Tensor) -> Tensor:
        rows, length, _ = tokens.shape
        head_dim = D_MODEL // JSA_HEADS

        def split(value: Tensor) -> Tensor:
            return value.view(rows, length, JSA_HEADS, head_dim).transpose(1, 2)

        query, key, value = split(self.query(tokens)), split(self.key(tokens)), split(
            self.value(tokens))
        scores = query @ key.transpose(-1, -2) / math.sqrt(head_dim)
        bias = -F.softplus(self.decay).view(1, JSA_HEADS, 1, 1) * log_delta.unsqueeze(1)
        allowed = causal.unsqueeze(1) & (valid > 0).view(rows, 1, 1, length)
        scores = torch.where(allowed, scores + bias,
                             torch.full_like(scores, torch.finfo(scores.dtype).min))
        # A row with no admissible key (a left pad) must produce exactly zero.
        has_key = allowed.any(dim=-1, keepdim=True)
        weights = torch.where(has_key, torch.softmax(scores, dim=-1),
                              torch.zeros_like(scores))
        context = (weights @ value).transpose(1, 2).reshape(rows, length, D_MODEL)
        return self.out(context) * valid.unsqueeze(-1)


class JSATokenMLP(nn.Module):
    """JSA_CAPACITY_MATCH: "every attention block replaced by an equal-parameter
    per-token MLP".  Attention holds 4*64*64 = 16,384 bias-free parameters; a
    bias-free 64->128->64 per-token MLP holds 8,192+8,192 = 16,384.  The only
    residue is the 16 lambda_h scalars, which is exactly the tolerance §5 names.
    """

    def __init__(self) -> None:
        super().__init__()
        self.up = nn.Linear(D_MODEL, JSA_FFN, bias=False)
        self.down = nn.Linear(JSA_FFN, D_MODEL, bias=False)

    def forward(self, tokens: Tensor, valid: Tensor, log_delta: Tensor,
                causal: Tensor) -> Tensor:
        del log_delta, causal   # a bag of native tokens: no cross-token interaction
        return self.down(F.silu(self.up(tokens))) * valid.unsqueeze(-1)


class JSABlock(nn.Module):
    """Pre-norm block: mix sublayer + bias-free FFN 64->128->64."""

    def __init__(self, attention: bool) -> None:
        super().__init__()
        self.norm_mix = nn.LayerNorm(D_MODEL)
        self.mix = JSAAttention() if attention else JSATokenMLP()
        self.norm_ffn = nn.LayerNorm(D_MODEL)
        self.up = nn.Linear(D_MODEL, JSA_FFN, bias=False)
        self.down = nn.Linear(JSA_FFN, D_MODEL, bias=False)

    def forward(self, tokens: Tensor, valid: Tensor, log_delta: Tensor,
                causal: Tensor) -> Tensor:
        mask = valid.unsqueeze(-1)
        tokens = tokens + self.mix(self.norm_mix(tokens) * mask, valid, log_delta, causal)
        tokens = tokens + self.down(F.silu(self.up(self.norm_ffn(tokens) * mask))) * mask
        return tokens * mask


class JSAModule(nn.Module):
    """§5 5b.  Tokens are the merged chronological union of the last M=192
    timestamp groups across the three modalities; each token is the SAME shared
    64d base group embedding + a learned 3x64 modality-type embedding + the
    shared 2x64 phase embedding; readout is mean+max -> bias-free 128->64."""

    def __init__(self, projections: Sequence[GroupProjection], phase: PhaseTable,
                 attention: bool) -> None:
        super().__init__()
        self._projections = tuple(projections)
        self._phase = (phase,)
        self.type_embedding = nn.Parameter(
            torch.empty(len(MODALITIES), D_MODEL).normal_())   # torch embedding default
        self.blocks = nn.ModuleList([JSABlock(attention) for _ in range(JSA_BLOCKS)])
        self.readout = nn.Linear(2 * D_MODEL, D_MODEL, bias=False)
        self.ablate_type_embedding = False   # §7 control (n), eval-time only

    def forward(self, batch: Batch, group_embedding: Sequence[Tensor]) -> Tensor:
        valid = (batch.jsa_mod >= 0).to(group_embedding[0].dtype)
        tokens = torch.zeros(batch.jsa_mod.shape + (D_MODEL,),
                             dtype=group_embedding[0].dtype,
                             device=batch.jsa_mod.device)
        for index in range(len(MODALITIES)):
            selected = (batch.jsa_mod == index)
            slot = torch.where(selected, batch.jsa_slot, torch.full_like(batch.jsa_slot, -1))
            gathered, _ = _gather_rows(group_embedding[index], slot)
            if not self.ablate_type_embedding:
                gathered = gathered + self.type_embedding[index]
            tokens = tokens + gathered * selected.unsqueeze(-1).to(tokens.dtype)
        tokens = (tokens + self._phase[0](batch.jsa_phase)) * valid.unsqueeze(-1)

        stamp = batch.jsa_ts_us
        delta = stamp.unsqueeze(2) - stamp.unsqueeze(1)          # t_i - t_j
        causal = (delta >= 0) & (valid > 0).unsqueeze(2) & (valid > 0).unsqueeze(1)
        log_delta = torch.log1p(delta.clamp_min(0).to(torch.float64)).to(tokens.dtype)

        for block in self.blocks:
            tokens = block(tokens, valid, log_delta, causal)
        mask = valid.unsqueeze(-1)
        pooled = torch.cat([masked_mean(tokens, mask, 1), masked_max(tokens, mask, 1)], dim=1)
        return self.readout(pooled)


# --- the arms --------------------------------------------------------------


class Arm(nn.Module):
    """One rung of §5's frozen ladder.  Every rung shares the same head shapes
    and the same additive-logit law; only the modality embeddings differ."""

    def __init__(self, name: str, interaction_outputs: int = N_OUT) -> None:
        super().__init__()
        if name in REPLAY_ONLY_ARMS:
            name = REPLAY_ONLY_ARMS[name]
        if name not in ARM_NAMES:
            raise ValueError(f"{name!r} is not a §5 arm; the ladder is {ARM_NAMES}")
        self.name = name
        native = name in ("NATIVE_ORDER", "NATIVE_INTERACTION",
                          "JOINT_STREAM_ATTENTION", "JSA_CAPACITY_MATCH")

        self.state_encoder = StateEncoder()
        self.market_heads = nn.ModuleList([Head(bias=False) for _ in MODALITIES])
        self.state_head = Head(bias=True)

        self.direct_encoders = nn.ModuleList()
        if name == "DIRECT_CAPACITY_MATCH":
            for _ in MODALITIES:
                self.direct_encoders.append(
                    nn.ModuleList([DirectEncoder()
                                   for _ in range(DIRECT_CAPACITY_MATCH_ENCODERS)])
                )
        elif name != "CLOCK_STATE":
            for _ in MODALITIES:
                self.direct_encoders.append(nn.ModuleList([DirectEncoder()]))

        self.group_projections = nn.ModuleList()
        self.micro_carriers = nn.ModuleList()
        self.bin_carriers = nn.ModuleList()
        self.phase_table = PhaseTable() if native else None
        if native:
            for modality in MODALITIES:
                projection = GroupProjection(GROUP_INPUTS[modality])
                self.group_projections.append(projection)
                self.micro_carriers.append(MicroCarrier(projection, self.phase_table))
                self.bin_carriers.append(BinCarrier())

        self.interaction = (NativeInteraction(interaction_outputs)
                            if name == "NATIVE_INTERACTION" else None)
        # §7 (h) is an INTERACTION-ONLY derangement: it permutes the option
        # operand that reaches the rank-8 term and "must preserve every additive
        # logit bit-for-bit".  The hook exists so that law is structural rather
        # than a hope: the additive path never sees the permutation.
        self.interaction_option_permutation: Tensor | None = None
        self.jsa = None
        self.jsa_head = None
        if name in ("JOINT_STREAM_ATTENTION", "JSA_CAPACITY_MATCH"):
            self.jsa = JSAModule(list(self.group_projections), self.phase_table,
                                 attention=(name == "JOINT_STREAM_ATTENTION"))
            self.jsa_head = Head(bias=False)

    # --- forward -----------------------------------------------------------

    def modality_embeddings(self, batch: Batch) -> list[Tensor]:
        rows = batch.rows
        device = batch.direct.device
        zero = torch.zeros(rows, D_MODEL, dtype=batch.direct.dtype, device=device)
        if self.name == "CLOCK_STATE":
            return [zero.clone() for _ in MODALITIES]

        out: list[Tensor] = []
        group_embedding = self.group_embeddings(batch)
        for index in range(len(MODALITIES)):
            embedding = zero.clone()
            for encoder in self.direct_encoders[index]:
                embedding = embedding + encoder(batch.direct[:, index, :])
            if self.micro_carriers:
                embedding = embedding + self.micro_carriers[index](
                    group_embedding[index], batch.micro_slot[:, index],
                    batch.micro_phase[:, index], batch.micro_ckpt[:, index],
                )
                embedding = embedding + self.bin_carriers[index](
                    group_embedding[index], batch.bin_slot[:, index]
                )
            out.append(embedding)
        return out

    def group_embeddings(self, batch: Batch) -> list[Tensor]:
        """§5's once-per-session/side/modality shared raw group projection."""
        if not self.group_projections:
            return [batch.groups[i].new_zeros(batch.groups[i].shape[0], D_MODEL)
                    for i in range(len(MODALITIES))]
        return [self.group_projections[i](batch.groups[i]) for i in range(len(MODALITIES))]

    def forward(self, batch: Batch) -> Tensor:
        market = self.modality_embeddings(batch)
        state = self.state_encoder(batch)
        logits = self.state_head(state)
        for index in range(len(MODALITIES)):
            logits = logits + self.market_heads[index](market[index])
        if self.jsa is not None:
            logits = logits + self.jsa_head(self.jsa(batch, self.group_embeddings(batch)))
        if self.interaction is not None:
            reliability = batch.r_modality
            weight = (reliability[:, 0] + reliability[:, 1]).clamp_min(1e-12)
            stock = (reliability[:, 0:1] * market[0] + reliability[:, 1:2] * market[1]) / \
                weight.unsqueeze(-1)
            both_absent = ((reliability[:, 0] + reliability[:, 1]) <= 0).unsqueeze(-1)
            stock = torch.where(both_absent, torch.zeros_like(stock), stock)
            r_state = torch.clamp(batch.visible_count / 4.0, max=1.0)
            gate = (torch.clamp(torch.maximum(reliability[:, 0], reliability[:, 1]), min=0.0)
                    * reliability[:, 2].clamp_min(0.0) * r_state) ** (1.0 / 3.0)
            option = market[2]
            if self.interaction_option_permutation is not None:
                option = option[self.interaction_option_permutation]
            logits = logits + self.interaction(stock, option, state, gate)
        return logits

    # --- capacity ----------------------------------------------------------

    def unique_parameter_count(self) -> int:
        seen: dict[int, int] = {}
        for parameter in self.parameters():
            seen[id(parameter)] = parameter.numel()
        return sum(seen.values())

    def declared_capacity(self) -> dict[str, int]:
        """§5's per-module algebra for the modules this arm actually builds."""
        table: dict[str, int] = {}
        for index, modality in enumerate(MODALITIES):
            if self.direct_encoders:
                table[f"direct_encoder_{modality}"] = \
                    self.direct_encoders[index][0].declared_parameter_count()
                if len(self.direct_encoders[index]) == DIRECT_CAPACITY_MATCH_ENCODERS:
                    table[f"direct_capacity_match_{modality}"] = sum(
                        encoder.declared_parameter_count()
                        for encoder in self.direct_encoders[index]
                    )
            if self.micro_carriers:
                micro = self.micro_carriers[index].declared_parameter_count()
                binc = self.bin_carriers[index].declared_parameter_count()
                direct = self.direct_encoders[index][0].declared_parameter_count()
                table[f"micro_{modality}"] = micro
                table[f"bin_carrier_{modality}"] = binc
                table[f"native_encoder_{modality}"] = direct + micro + binc
        if self.jsa is not None:
            table["jsa_module"] = sum(p.numel() for p in self.jsa.parameters())
        return table


def build_arm(name: str, *, interaction_outputs: int = N_OUT) -> Arm:
    return Arm(name, interaction_outputs=interaction_outputs)


def frozen_capacity_report() -> list[tuple[str, int, int, bool]]:
    """(label, built, frozen, agrees) for each of §5's nine pinned numbers."""
    native = build_arm("NATIVE_ORDER")
    capacity = native.declared_capacity()
    match = build_arm("DIRECT_CAPACITY_MATCH").declared_capacity()
    built = {
        "direct_encoder": capacity["direct_encoder_stock_print"],
        "micro_stock_print": capacity["micro_stock_print"],
        "micro_stock_nbbo": capacity["micro_stock_nbbo"],
        "micro_option_print": capacity["micro_option_print"],
        "bin_carrier": capacity["bin_carrier_stock_print"],
        "native_encoder_stock_print": capacity["native_encoder_stock_print"],
        "native_encoder_stock_nbbo": capacity["native_encoder_stock_nbbo"],
        "native_encoder_option_print": capacity["native_encoder_option_print"],
        "direct_capacity_match_per_modality": match["direct_capacity_match_stock_print"],
    }
    # §5 also pins the three bin carriers as identical; prove it rather than assume.
    for modality in MODALITIES:
        assert capacity[f"bin_carrier_{modality}"] == built["bin_carrier"], modality
    return [(label, built[label], FROZEN_CAPACITY[label],
             built[label] == FROZEN_CAPACITY[label]) for label in FROZEN_CAPACITY]


def assert_frozen_capacities() -> None:
    wrong = [row for row in frozen_capacity_report() if not row[3]]
    if wrong:
        raise AssertionError(f"§5 capacity algebra violated: {wrong}")


def capacity_gaps() -> dict[str, float]:
    """§5: "gaps 4.53%/4.67%/3.84%" of DIRECT_CAPACITY_MATCH over each native."""
    match = FROZEN_CAPACITY["direct_capacity_match_per_modality"]
    return {
        modality: (match - FROZEN_CAPACITY[f"native_encoder_{modality}"])
        / FROZEN_CAPACITY[f"native_encoder_{modality}"] * 100.0
        for modality in MODALITIES
    }
