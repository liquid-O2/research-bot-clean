"""synth.py — synthetic C4-shaped DecisionTape shards.  SYNTHETIC ONLY.

LAWFULNESS.  Nothing here reads market data.  Every array is generated from a
seeded PCG64 stream, and `assert_synthetic_only()` refuses any path under the
real tensor root, so a training run pointed at these shards provably never
touches /workspace/artifacts/tensors/v4.0.  The shards are written through the
same .npy + manifest.tsv contract the C++ writer publishes, and are read back
through the EXISTING `decision_tape_loader.DecisionTape` — the truth allowlist
is honoured, never widened.

WHAT THE SHARD CARRIES.  FINAL_PLAN APPENDIX C4 names the leaves; TASK CARD V4
§4/§5 fix their contents.  Two spellings C4 leaves implicit are made explicit
here:

  * `groups_{mod}` carries a PER-MODALITY group axis (G_sp, G_nb, G_op differ).
    §5 5b's JSA tokens are "the merged chronological union of the last M=192
    timestamp groups ACROSS the three modalities", which is only meaningful if
    the three axes are separate before they are merged.  `group_ts` is therefore
    also per modality.  RULED CONFIRMED (2026-08-11).
  * the carriers are stored as gather INDICES into that axis (C4's
    `recent128 [N,2]` / `bins_index [N,120,2]` are (start,len) forms of the same
    thing); this module stores explicit slot vectors so a pad is a literal -1
    and no arithmetic can silently invent a group.

>>> BINDING RULE (orchestrator, 2026-08-11).  THE C++ TAPE IS THE AUTHORITY.
This module is a stand-in that exists only so the arms and the controls can be
proven before the corpus lands.  When the real corpus arrives, read the REAL
s0125 manifest and bind `assemble()` (and the loader) to the EMITTED leaf names
and to C4's (start,len) CSR forms exactly as the tape spells them.  ADAPT THE
ASSEMBLER, NEVER THE TAPE -- the explicit slot vectors below are this file's
convenience, not a request to the emitter.  `arms.py` is layout-independent (it
consumes the `Batch` dataclass), so this rebinding is confined to `assemble()`.

CHANNEL TABLES.  The σ/own-opposite tables below are transcribed from §4's own
channel lists (stock-print 17, stock-NBBO 16, option-print 22) and §5's location
(16) and candidate (24) lists.  They are the law for control (i).

GROUP VECTOR LAYOUT.  §5: "equal-time mean+max over 17 values+17 masks plus log
multiplicity is 69 inputs" (65 / 89 for NBBO / option).  This module lays that
out as [mean_values(V), mean_masks(V), max_values(V), max_masks(V), log_mult],
so 4V+1 = 69/65/89 exactly.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from decision_tape_loader import DecisionTape  # noqa: E402

import arms  # noqa: E402
import tapes  # noqa: E402

# The real tensor root.  This module must never produce or accept a path here.
REAL_TENSOR_ROOTS = ("/workspace/artifacts/tensors/v4.0", "/workspace/data/tokens")

MANIFEST_SCHEMA = "qr_emit_manifest_v1"
SYNTH_BUILD_ID = "campaign_synth_v1"

# The trainer's explicit truth allowlist.  §3: "the trainer opens an explicit
# truth allowlist for loss computation only".  NEVER widen this list.
TRUTH_ALLOWLIST = (
    "menu_net_cent",
    "cert_net_cent",
    "stop_hit",
    "barrier",
    "label_state",
    "keys",
)

VALUE_CHANNELS = {"stock_print": 17, "stock_nbbo": 16, "option_print": 22}

# §4 channel lists, transcribed.  SIGMA = multiplied by sigma (+1 LONG, -1 SHORT).
SIGMA_CHANNELS = {
    # log interarrival(0) | return(1) | print-minus-mid(2) | aggressor(3) |
    # log size(4) | signed size(5) | spread(6) | own/opp attached size(7,8) |
    # size imbalance(9) | quote age(10) | quote-present(11) | attach-valid(12) |
    # seq gap(13) | seq monotone(14) | same-ms(15) | directional-eligible(16)
    "stock_print": (1, 2, 3, 5, 9),
    # interarrival(0) | mid change(1) | spread(2) | own/opp size(3,4) |
    # imbalance(5) | own/opp price change(6,7) | own/opp signed size change(8,9) |
    # locked(10) crossed(11) two-sided(12) bid-changed(13) ask-changed(14) same-ms(15)
    "stock_nbbo": (1, 5),
    # interarrival(0) | underlying return(1) | right direction(2) | aggressor(3) |
    # log size(4) | signed premium flow(5) | print-minus-mid(6) | spread(7) |
    # delta(8) | gamma(9) | vanna(10) | charm(11) | IV(12) | log DTE(13) |
    # moneyness(14) | delta/gamma/vanna/charm flow(15,16,17,18) |
    # quote age(19) | underlying age(20) | directional-eligible(21)
    # §4: "Gamma and recomputed gamma-flow remain side-invariant."
    "option_print": (1, 2, 3, 5, 6, 8, 10, 11, 14, 15, 17, 18),
}
OWN_OPPOSITE_PAIRS = {
    "stock_print": ((7, 8),),
    "stock_nbbo": ((3, 4), (6, 7), (8, 9)),
    "option_print": (),
}

# §4 DIRECT: 4 windows x [log count, valid fraction, mean/last of 4 mechanisms]
# then 20 full-window statistics.  Only the mechanism columns can be oriented.
DIRECT_WINDOWS = 4
DIRECT_WINDOW_COLUMNS = 10
DIRECT_FULL_WINDOW_COLUMNS = 20
# mechanism index (0..3) that carries sigma, per modality:
#   stock print: return / aggressor / signed-size / imbalance  -> all oriented
#   NBBO:        mid-change / spread / imbalance / own-size-change
#   option:      underlying-return / aggressor / premium-flow / delta-flow
DIRECT_SIGMA_MECHANISMS = {
    "stock_print": (0, 1, 2, 3),
    "stock_nbbo": (0, 2),
    "option_print": (0, 1, 2, 3),
}
# NBBO's 4th DIRECT mechanism is "own-size-change": its reflected value is the
# OPPOSITE side's size change, which a LONG summary does not carry.  The
# synthetic generator therefore emits a reflection-symmetric value for it
# (bid and ask size change equal), declared, so control (i) stays exact.
DIRECT_NONINVERTIBLE = {"stock_nbbo": (3,)}

# §5 location list (16): 0 session-time fraction, 1 sin, 2 cos, 3 seconds-to-close
# fraction, 4 early-close, 5 bps from open, 6 bps from high, 7 bps from low,
# 8 range bps, 9 bps from VWAP, 10/11/12 RV 1s/5s/30s, 13 spread bps,
# 14 since-last-stock-print, 15 since-last-option-print.
LOCATION_SIGMA = (5, 6, 7, 9)
SESSION_TIME_FRACTION_INDEX = 0   # §7 (a)/(b): "the always-present session-time-
                                  # fraction scalar" that the injections replace

# §5 candidate fields (24): 0..11 policy one-hot, 12 reversal/20, 13 log1p member
# count, 14 log1p age, 15..18 own/opposite/mixed/unavailable relation one-hot,
# 19..23 visibility-in-last-{1,5,15,30,60}s.
CANDSET_OWN_INDEX = 15
CANDSET_OPPOSITE_INDEX = 16

SIDES = ("L", "S")
SIDE_SIGMA = {"L": 1.0, "S": -1.0}
NPY_DTYPES = {np.dtype("<i8"): "<i8", np.dtype("<i4"): "<i4",
              np.dtype("<f4"): "<f4", np.dtype("|u1"): "|u1"}


def assert_synthetic_only(paths: Sequence[str]) -> None:
    """Refuses if any path touches the real tensor/token roots."""
    offenders = [path for path in paths
                 if any(str(path).startswith(root) for root in REAL_TENSOR_ROOTS)]
    if offenders:
        raise AssertionError(f"a synthetic-only run touched real data: {offenders}")


# --- shard specification ---------------------------------------------------


@dataclass
class SynthSpec:
    """The knobs of one synthetic session.  Sizes are small on purpose: §5's
    frozen carrier lengths (128 / 120 / 192) are honoured, the token supply
    behind them is not."""

    session_ordinal: int = 125
    rows: int = 24
    groups: tuple[int, int, int] = (48, 40, 32)
    candidates: int = 8
    bin_slots: int = 2
    seed: int = 20260810
    signal: str = "random"        # random | xor | linear
    label_noise: float = 0.0
    stop_level_cent: int = -12_000
    # noise_scale multiplies every non-planted VALUE channel (masks and presence
    # bits are untouched).  The §7 control harnesses run at 0.0 so the planted
    # mechanism is the ONLY information in the tape: with nothing to memorise,
    # an arm that clears the bar can only have represented the mechanism, which
    # is exactly what controls (a)/(b)/(c) assert.
    noise_scale: float = 1.0
    field_overrides: dict = field(default_factory=dict)


def _npy_bytes(array: np.ndarray) -> bytes:
    import io

    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _write_leaf(root: pathlib.Path, section: str, name: str,
                array: np.ndarray) -> tuple[str, int]:
    directory = root / section
    directory.mkdir(parents=True, exist_ok=True)
    payload = _npy_bytes(np.ascontiguousarray(array))
    path = directory / f"{name}.npy"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    shape = ",".join(str(int(extent)) for extent in array.shape)
    row = (f"leaf\t{section}/{name}.npy\t{NPY_DTYPES[array.dtype]}\t{shape}"
           f"\t{int(array.shape[0])}\t{digest}")
    return row, len(payload)


def _generate(spec: SynthSpec, side: str) -> tuple[dict, dict]:
    """Builds the feature and truth arrays of one (session, side) shard.

    A SHORT shard is the exact lawful reflection of the LONG shard of the same
    session: the same underlying draw, run through the §4 orientation law.  That
    is what makes control (i) an equality test rather than an approximation.
    """
    rng = np.random.default_rng(np.random.SeedSequence(
        [spec.seed, spec.session_ordinal, 0]))   # side-independent draw
    sigma = SIDE_SIGMA[side]
    rows, candidates = spec.rows, spec.candidates
    counts = dict(zip(arms.MODALITIES, spec.groups))
    noise = float(spec.noise_scale)

    features: dict[str, np.ndarray] = {}

    # --- per-modality group axes ------------------------------------------
    for index, modality in enumerate(arms.MODALITIES):
        values = VALUE_CHANNELS[modality]
        total = counts[modality]
        mean_v = (noise * rng.normal(0.0, 1.0, (total, values))).astype(np.float32)
        max_v = mean_v + (noise * np.abs(rng.normal(0.0, 0.3, (total, values)))
                          ).astype(np.float32)
        mean_m = (rng.random((total, values)) > 0.1).astype(np.float32)
        max_m = mean_m.copy()
        if modality == "stock_nbbo":
            # declared: keep the own/opposite size-change pair symmetric so the
            # DIRECT own-size-change column is reflection-invariant (see above)
            mean_v[:, 9] = mean_v[:, 8]
            max_v[:, 9] = max_v[:, 8]
        log_mult = np.log1p(rng.integers(1, 4, (total, 1))).astype(np.float32)
        block = np.concatenate([mean_v, mean_m, max_v, max_m, log_mult], axis=1)
        block = _reflect_group_block(block, modality, sigma)
        assert block.shape[1] == arms.GROUP_INPUTS[modality]
        features[f"groups_{modality}"] = block.astype(np.float32)
        stamps = np.cumsum(rng.integers(1, 40_000, total)).astype(np.int64)
        features[f"group_ts_{modality}"] = stamps

    # --- DIRECT summaries --------------------------------------------------
    direct = (noise * rng.normal(0.0, 1.0, (rows, len(arms.MODALITIES),
                                            arms.DIRECT_COLUMNS))).astype(np.float32)
    direct[:, :, DIRECT_WINDOWS * DIRECT_WINDOW_COLUMNS:] = np.abs(
        direct[:, :, DIRECT_WINDOWS * DIRECT_WINDOW_COLUMNS:])
    for index, modality in enumerate(arms.MODALITIES):
        for blind in DIRECT_NONINVERTIBLE.get(modality, ()):
            for window in range(DIRECT_WINDOWS):
                base = window * DIRECT_WINDOW_COLUMNS + 2 + 2 * blind
                direct[:, index, base:base + 2] = np.abs(direct[:, index, base:base + 2])
    direct = _reflect_direct(direct, sigma)
    features["direct_raw"] = direct
    features["r_modality"] = np.ones((rows, len(arms.MODALITIES)), dtype=np.float32)

    # --- state block -------------------------------------------------------
    candset = np.zeros((rows, candidates, arms.CANDSET_FIELDS), dtype=np.float32)
    policy = rng.integers(0, 12, (rows, candidates))
    for row in range(rows):
        for slot in range(candidates):
            candset[row, slot, policy[row, slot]] = 1.0
    candset[:, :, 12] = noise * rng.normal(0.0, 0.5, (rows, candidates))
    candset[:, :, 13] = noise * np.log1p(rng.integers(1, 6, (rows, candidates)))
    candset[:, :, 14] = noise * np.log1p(rng.random((rows, candidates)) * 60.0)
    relation = rng.integers(0, 4, (rows, candidates))
    for choice in range(4):
        candset[:, :, 15 + choice] = (relation == choice).astype(np.float32)
    candset[:, :, 19:24] = (rng.random((rows, candidates, 5)) > 0.5).astype(np.float32)
    candset = _reflect_candset(candset, sigma)
    features["candset"] = candset
    features["candset_len"] = rng.integers(1, candidates + 1, rows).astype(np.int32)

    location = np.zeros((rows, arms.LOCATION_INPUTS), dtype=np.float32)
    location[:, :arms.LOCATION_VALUES] = noise * rng.normal(
        0.0, 1.0, (rows, arms.LOCATION_VALUES))
    location[:, 0] = np.linspace(0.05, 0.95, rows)                # session-time fraction
    location[:, arms.LOCATION_VALUES:] = 1.0   # §5: the five pure clock values
                                               # are always present; synth keeps
                                               # every location channel present
    location = _reflect_location(location, sigma)
    features["locclock"] = location
    features["visible_count"] = features["candset_len"].astype(np.int32)

    # --- carriers ----------------------------------------------------------
    for index, modality in enumerate(arms.MODALITIES):
        total = counts[modality]
        slot = np.full((rows, arms.MICRO_LENGTH), -1, dtype=np.int32)
        phase = np.full((rows, arms.MICRO_LENGTH), 2, dtype=np.uint8)
        for row in range(rows):
            length = int(rng.integers(max(1, total // 2), total + 1))
            length = min(length, arms.MICRO_LENGTH)
            slot[row, arms.MICRO_LENGTH - length:] = np.arange(total - length, total)
            split = int(rng.integers(0, length + 1))
            phase[row, arms.MICRO_LENGTH - length:arms.MICRO_LENGTH - length + split] = 0
            phase[row, arms.MICRO_LENGTH - length + split:] = 1
            if split < length:
                phase[row, arms.MICRO_LENGTH - length + split] = 2   # PHASE_EQUAL_UNORDERED
        features[f"micro_slot_{modality}"] = slot
        features[f"micro_phase_{modality}"] = phase
        checkpoint = np.full((rows, len(arms.CHECKPOINT_OFFSETS_S)), -1, dtype=np.int32)
        for row in range(rows):
            present = np.nonzero(slot[row] >= 0)[0]
            for offset_index in range(len(arms.CHECKPOINT_OFFSETS_S)):
                if offset_index < present.size:
                    checkpoint[row, offset_index] = int(present[-1 - offset_index])
        features[f"micro_ckpt_{modality}"] = checkpoint
        # The emitted form: `bins_index [N,120,2]` (start,len) CSR over the
        # group axis, where a bin is an absolute session SECOND and every row
        # spanning that second carries the same (start,len) — the invariant this
        # writer must reproduce, because the loader dedupes on it.
        per_second = max(1, total // (rows + arms.BIN_LENGTH))
        bins = np.zeros((rows, arms.BIN_LENGTH, 2), dtype=np.int32)
        row_index = np.arange(rows)[:, None]
        bin_index = np.arange(arms.BIN_LENGTH)[None, :]
        second = row_index + bin_index
        start = second * per_second
        length = np.clip(total - start, 0, per_second)
        # The pre-open pad: a bin before the session's first second is typed -1.
        pad = second < arms.BIN_LENGTH
        bins[..., 0] = np.where(pad | (length <= 0), -1, start)
        bins[..., 1] = np.where(pad | (length <= 0), 0, length)
        features[f"bins_index_{modality}"] = bins

    # --- JSA merged token stream ------------------------------------------
    merged = []
    for index, modality in enumerate(arms.MODALITIES):
        stamps = features[f"group_ts_{modality}"]
        merged.extend((int(stamps[g]), index, g) for g in range(counts[modality]))
    merged.sort()
    merged = merged[-arms.JSA_TOKENS:]
    jsa_mod = np.full((rows, arms.JSA_TOKENS), -1, dtype=np.int32)
    jsa_slot = np.full((rows, arms.JSA_TOKENS), -1, dtype=np.int32)
    jsa_phase = np.full((rows, arms.JSA_TOKENS), 2, dtype=np.uint8)
    jsa_ts = np.zeros((rows, arms.JSA_TOKENS), dtype=np.int64)
    start = arms.JSA_TOKENS - len(merged)
    for row in range(rows):
        for position, (stamp, modality_index, group) in enumerate(merged):
            jsa_mod[row, start + position] = modality_index
            jsa_slot[row, start + position] = group
            jsa_ts[row, start + position] = stamp
            jsa_phase[row, start + position] = 0 if position < len(merged) // 2 else 1
    features["jsa_mod"] = jsa_mod
    features["jsa_slot"] = jsa_slot
    features["jsa_phase"] = jsa_phase
    features["jsa_ts_us"] = jsa_ts

    keys = np.zeros((rows, 4), dtype=np.int64)
    keys[:, 0] = spec.session_ordinal
    keys[:, 1] = np.arange(rows)
    # THE REAL COLUMN ORDER (qr_replay/action.hpp `ActionKey`, and the emitted
    # s0125 tape): (session_ordinal, decision_ordinal, decision_ts_ns, side).
    # §3: decision timestamps are registered whole seconds off the session start.
    keys[:, tapes.KEY_TS] = 1_600_000_000_000_000_000 + np.arange(rows) * 60_000_000_000
    keys[:, tapes.KEY_SIDE] = tapes.KEY_SIGMA[side]   # sigma, +1 / -1
    features["keys"] = keys
    # §6 stage mask: which of D0/D30/D60 support this row (bits 1/2/4).  It is
    # causal ledger metadata, never a model input; the controls bucket on it.
    features["stage_mask"] = (rng.integers(1, 8, rows)).astype(np.uint8)

    # --- truth -------------------------------------------------------------
    label_rng = np.random.default_rng(np.random.SeedSequence(
        [spec.seed, spec.session_ordinal, SIDES.index(side), 7]))
    net = label_rng.normal(0.0, 12_000.0, (rows, arms.N_MENU_HORIZONS))
    if spec.signal == "xor":
        # §7 (c) "balanced XOR": the sign of net_h_ref is the PRODUCT of one
        # stock DIRECT channel's sign and one option DIRECT channel's sign.  The
        # four cells are drawn in equal numbers from a session-level (not
        # row-index, not side) stream, so no additive function of any single
        # input — including the clock — carries information about the target.
        plant = np.random.default_rng(np.random.SeedSequence(
            [spec.seed, spec.session_ordinal, 99]))
        cells = np.tile(np.arange(4), int(np.ceil(rows / 4)))[:rows]
        cells = plant.permutation(cells)
        first = np.where(cells % 2 == 0, 1.0, -1.0)
        second = np.where(cells // 2 == 0, 1.0, -1.0)
        features["direct_raw"][:, 0, 2] = first
        features["direct_raw"][:, 2, 2] = second
        target = first * second
        if spec.label_noise:
            flip = plant.random(rows) < spec.label_noise
            target = np.where(flip, -target, target)
        net[:, arms.H_REF_INDEX] = target * 8_000.0
    elif spec.signal == "linear":
        net[:, arms.H_REF_INDEX] = features["direct_raw"][:, 0, 2] * 9_000.0

    leaves: dict[str, np.ndarray] = {}
    leaves["menu_net_cent"] = np.clip(net, -30_000, 10 ** 9).astype(np.int64)
    leaves["menu_mae_cent"] = np.abs(net).astype(np.int64)
    leaves["menu_exit_ts"] = (keys[:, 3:4] + np.arange(1, 8) * 60_000_000_000).astype(np.int64)
    # SYNTHETIC stop level.  The real $300 wall is the C++ label kernel's (§3);
    # synth's job is shape and planted structure, and a wall that fires on <1% of
    # rows would leave the risk-head controls with no positives to rank.
    leaves["stop_hit"] = (net <= spec.stop_level_cent).astype(np.uint8)
    leaves["cert_net_cent"] = np.max(net, axis=1).astype(np.int64)
    leaves["cert_mae_cent"] = np.abs(net).max(axis=1).astype(np.int64)
    leaves["barrier"] = label_rng.integers(0, 3, rows).astype(np.uint8)
    # §3 label states: 0 OK, 1 ENTRY_UNAVAILABLE, 2 EXIT_UNAVAILABLE.  Every row
    # is retained and predicted; only the LOSS is availability-masked.
    leaves["label_state"] = np.zeros(rows, dtype=np.uint8)
    leaves["label_state"][label_rng.random(rows) < 0.05] = 1
    leaves["keys"] = keys
    for name, value in spec.field_overrides.items():
        section, leaf = name.split("/")
        (features if section == "features" else leaves)[leaf] = value
    return features, leaves


def _reflect_group_block(block: np.ndarray, modality: str, sigma: float) -> np.ndarray:
    if sigma > 0:
        return block
    values = VALUE_CHANNELS[modality]
    out = block.copy()
    for offset in (0, 2 * values):                       # mean values, max values
        for channel in SIGMA_CHANNELS[modality]:
            out[..., offset + channel] *= -1.0
    for offset in (0, values, 2 * values, 3 * values):   # values AND their masks
        for own, opposite in OWN_OPPOSITE_PAIRS[modality]:
            left = out[..., offset + own].copy()
            out[..., offset + own] = out[..., offset + opposite]
            out[..., offset + opposite] = left
    return out


def _reflect_direct(direct: np.ndarray, sigma: float) -> np.ndarray:
    if sigma > 0:
        return direct
    out = direct.copy()
    for index, modality in enumerate(arms.MODALITIES):
        for mechanism in DIRECT_SIGMA_MECHANISMS[modality]:
            for window in range(DIRECT_WINDOWS):
                base = window * DIRECT_WINDOW_COLUMNS + 2 + 2 * mechanism
                out[:, index, base:base + 2] *= -1.0
    return out


def _reflect_location(location: np.ndarray, sigma: float) -> np.ndarray:
    if sigma > 0:
        return location
    out = location.copy()
    for column in LOCATION_SIGMA:
        out[:, column] *= -1.0
    return out


def _reflect_candset(candset: np.ndarray, sigma: float) -> np.ndarray:
    if sigma > 0:
        return candset
    out = candset.copy()
    own = out[..., CANDSET_OWN_INDEX].copy()
    out[..., CANDSET_OWN_INDEX] = out[..., CANDSET_OPPOSITE_INDEX]
    out[..., CANDSET_OPPOSITE_INDEX] = own
    return out


def write_shard(base: pathlib.Path, spec: SynthSpec, side: str,
                *, features_only: bool = False) -> pathlib.Path:
    """Writes <base>/s<0125>/<L|S> exactly as the C++ writer composes it."""
    assert_synthetic_only([str(base)])
    root = pathlib.Path(base) / f"s{spec.session_ordinal:04d}" / side
    if root.exists():
        for entry in sorted(root.rglob("*")):
            if entry.is_file():
                entry.unlink()
    root.mkdir(parents=True, exist_ok=True)
    features, leaves = _generate(spec, side)
    rows: list[str] = []
    total = 0
    for name in sorted(features):
        row, size = _write_leaf(root, "features", name, features[name])
        rows.append(row)
        total += size
    if not features_only:
        for name in sorted(leaves):
            row, size = _write_leaf(root, "truth", name, leaves[name])
            rows.append(row)
            total += size
    header = [
        f"# {MANIFEST_SCHEMA}\tkind\tfields",
        f"meta\tmanifest_schema\t{MANIFEST_SCHEMA}",
        f"meta\tbuild_id\t{SYNTH_BUILD_ID}",
        f"meta\tsession_ordinal\t{spec.session_ordinal}",
        f"meta\tside\t{'LONG' if side == 'L' else 'SHORT'}",
        f"meta\tleaf_count\t{len(rows)}",
        f"meta\ttotal_leaf_bytes\t{total}",
        f"meta\tsignal\t{spec.signal}",
        "source\tsynthetic\t" + "0" * 64 + "\tsynthetic://campaign/synth",
        "census\tsynthetic\t" + "0" * 64 + "\tsynthetic://campaign/census",
    ]
    (root / "manifest.tsv").write_text("\n".join(header + rows) + "\n", encoding="utf-8")
    return root


def write_session(base: pathlib.Path, spec: SynthSpec) -> dict[str, pathlib.Path]:
    return {side: write_shard(base, spec, side) for side in SIDES}


# --- assembly --------------------------------------------------------------


@dataclass
class Targets:
    """A1's supervised quantities for one micro-batch, already normalised."""

    menu_net: torch.Tensor          # f32 [B,7]  net_h/30000
    menu_mask: torch.Tensor         # f32 [B,7]
    certificate: torch.Tensor       # f32 [B]
    certificate_mask: torch.Tensor  # f32 [B]
    opportunity: torch.Tensor       # f32 [B,3]
    risk: torch.Tensor              # f32 [B,2]
    barrier: torch.Tensor           # i64 [B]
    row_mask: torch.Tensor          # f32 [B]  label_state == OK
    keys: torch.Tensor              # i64 [B,4]
    stage_mask: torch.Tensor        # i64 [B]  causal ledger metadata (§6 stages)
    availability: torch.Tensor      # i64 [B]  §3 label_state, 0 OK

    def to(self, device: torch.device) -> "Targets":
        return Targets(**{name: getattr(self, name).to(device)
                          for name in self.__dataclass_fields__})


def _tensor(array, dtype) -> torch.Tensor:
    # copy=True: the leaves are read-only mmaps, and a torch view of a read-only
    # buffer is undefined behaviour the moment anything writes to it.
    return torch.from_numpy(np.array(array, copy=True)).to(dtype)


def build_targets(menu_net_cent, cert_net_cent, stop_hit, barrier, label_state,
                  keys, stage_mask) -> Targets:
    """Assembles A1's supervised bundle from ALREADY-RESOLVED label arrays.

    APPENDIX C4 forbids a truth array reaching a FEATURE tensor.  Keeping the
    label arithmetic in a function whose arguments are plain arrays — and which
    holds no feature tensor at all — makes that structural: this is the only
    place a label is shaped, and nothing here can see a feature.
    """
    net = _tensor(menu_net_cent, torch.float32)
    reference = net[:, arms.H_REF_INDEX]
    stop = _tensor(stop_hit, torch.float32)
    state = _tensor(label_state, torch.int64)
    row_mask = (state == 0).to(torch.float32)               # §3: OK only
    return Targets(
        menu_net=net / arms.NET_SCALE,
        menu_mask=row_mask.unsqueeze(1).expand(-1, arms.N_MENU_HORIZONS).contiguous(),
        certificate=_tensor(cert_net_cent, torch.float32) / arms.NET_SCALE,
        certificate_mask=row_mask.clone(),
        # A1 opportunity events on net_h_ref: >0, >=10,000c, >=30,000c.
        opportunity=torch.stack([(reference > 0).to(torch.float32),
                                 (reference >= 10_000).to(torch.float32),
                                 (reference >= 30_000).to(torch.float32)], dim=1),
        # A1 risk: stop before h_ref (primary) and before 60m (auxiliary).
        risk=torch.stack([stop[:, arms.H_REF_INDEX], stop[:, arms.H_60M_INDEX]], dim=1),
        barrier=_tensor(barrier, torch.int64),
        row_mask=row_mask,
        keys=_tensor(keys, torch.int64),
        stage_mask=_tensor(stage_mask, torch.int64),
        availability=state,
    )


def assemble(tape: DecisionTape) -> tuple[arms.Batch, Targets]:
    """Reads one published tape into the §5 Batch + A1 Targets.

    features() can never resolve a truth leaf and truth() is called with the
    frozen allowlist, so this function is the whole C4 door for the trainer.

    THIS IS THE REBINDING POINT (see the module BINDING RULE): when the real
    corpus lands, the emitted names and C4's (start,len) CSR forms are matched
    HERE, against the real s0125 manifest.  Nothing upstream of `arms.Batch`
    changes, and nothing about the tape changes.
    """
    features = tape.features()
    allowed = tape.truth(list(TRUTH_ALLOWLIST))

    # The bin carrier reads a per-second SEGMENT table, built from the emitted
    # (start,len) CSR by the same function the real door uses.
    bin_reference, bin_segment, bin_segment_count = {}, {}, {}
    for modality in arms.MODALITIES:
        index = np.asarray(features[f"bins_index_{modality}"])
        seg_start, seg_len, reference = tapes.bin_segments(index)
        total_groups = np.asarray(features[f"group_ts_{modality}"]).shape[0]
        assignment = np.full(total_groups, -1, dtype=np.int64)
        for segment in range(seg_start.shape[0]):
            low = int(seg_start[segment])
            assignment[low:low + int(seg_len[segment])] = segment
        bin_reference[modality] = reference
        bin_segment[modality] = assignment
        bin_segment_count[modality] = int(seg_start.shape[0])

    location = _tensor(features["locclock"], torch.float32)
    candidates = _tensor(features["candset"], torch.float32)
    lengths = _tensor(features["candset_len"], torch.int64)
    positions = torch.arange(candidates.shape[1]).unsqueeze(0)
    batch = arms.Batch(
        candset=candidates,
        candset_valid=(positions < lengths.unsqueeze(1)).to(torch.float32),
        loc_value=location[:, : arms.LOCATION_VALUES],
        loc_present=location[:, arms.LOCATION_VALUES:],
        visible_count=_tensor(features["visible_count"], torch.float32),
        direct=_tensor(features["direct_raw"], torch.float32),
        r_modality=_tensor(features["r_modality"], torch.float32),
        groups=tuple(_tensor(features[f"groups_{m}"], torch.float32)
                     for m in arms.MODALITIES),
        micro_slot=torch.stack([_tensor(features[f"micro_slot_{m}"], torch.int64)
                                for m in arms.MODALITIES], dim=1),
        micro_phase=torch.stack([_tensor(features[f"micro_phase_{m}"], torch.int64)
                                 for m in arms.MODALITIES], dim=1),
        micro_ckpt=torch.stack([_tensor(features[f"micro_ckpt_{m}"], torch.int64)
                                for m in arms.MODALITIES], dim=1),
        bin_ref=torch.stack([torch.from_numpy(bin_reference[m])
                             for m in arms.MODALITIES], dim=1),
        bin_seg=tuple(torch.from_numpy(bin_segment[m]) for m in arms.MODALITIES),
        bin_segments=tuple(bin_segment_count[m] for m in arms.MODALITIES),
        jsa_mod=_tensor(features["jsa_mod"], torch.int64),
        jsa_slot=_tensor(features["jsa_slot"], torch.int64),
        jsa_phase=_tensor(features["jsa_phase"], torch.int64),
        jsa_ts_us=_tensor(features["jsa_ts_us"], torch.int64),
    )

    targets = build_targets(stage_mask=features["stage_mask"],
                            **{name: allowed[name] for name in TRUTH_ALLOWLIST})
    assert_synthetic_only(tape.opened_paths)
    return batch, targets


def load_session(base: pathlib.Path, ordinal: int,
                 *, verify_sha: bool = False) -> dict[str, tuple[arms.Batch, Targets]]:
    out = {}
    for side in SIDES:
        tape = DecisionTape(pathlib.Path(base) / f"s{ordinal:04d}" / side,
                            verify_sha=verify_sha)
        out[side] = assemble(tape)
    return out


def build_corpus(base: pathlib.Path, ordinals: Sequence[int], **kwargs) -> list[int]:
    """Writes one synthetic session per ordinal and returns the ordinals."""
    for ordinal in ordinals:
        write_session(base, SynthSpec(session_ordinal=ordinal, **kwargs))
    return list(ordinals)
