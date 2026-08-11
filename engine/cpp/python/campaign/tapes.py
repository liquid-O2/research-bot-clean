"""tapes.py — THE C4 DOOR: one published DecisionTape -> the §5 Batch + A1 Targets.

THE TAPE IS THE AUTHORITY (orchestrator ruling, 2026-08-11).  Every name, dtype
and encoding below is read off the REAL emitted manifest
(`/workspace/artifacts/tensors/v4.0/run1/tapes/s0125/{L,S}/manifest.tsv`) and off
the emitter's own loader contract in
`qr_carriers/include/qr_carriers/native_emit.hpp`.  Where this module and the
tape disagree, THIS MODULE IS WRONG.

WHAT THE REAL TAPE ACTUALLY CARRIES, and the three things it does differently
from the synthetic stand-in that preceded it:

  1. SIDE-NEUTRAL GROUP STORAGE.  `groups_{mod}`, `group_ts_{mod}` and
     `orientation_{mod}` are written ONCE PER SESSION, into the LONG shard.  The
     SHORT shard has 28 leaves, not 37, and carries no group table at all: it
     reads its sibling's and applies the orientation law.  The stored width is
     `4C+1+S` (74/67/101), not the model's `4C+1` (69/65/89) — the tail is the
     finite MIN of each channel that negates under a side flip, which exists
     because `max(-x) = -min(x)` and a max does not commute with negation.
     `orient_group_vector` below is that law, transcribed from native_emit.hpp.

  2. THE CARRIERS ARE (start,len) CSR, and the bin carrier CANNOT be densified.
     Measured on session 125: NBBO bins hold 131 groups on average and up to
     621, so the old dense `[B,3,120,S]` slot tensor would be ~458 GB for one
     256-row micro-batch.  Measured, also on session 125: bins are absolute
     session-second segments SHARED BY EVERY ROW that spans them (row 100's
     bins[1:] are byte-identical to row 101's bins[:-1]).  So a bin is reduced
     ONCE per (session, modality, second) and rows reference the reduction.
     `bin_segments` builds that table; `arms.BinCarrier` consumes it.

  3. `keys [N,4]` is `(session_ordinal, decision_ordinal, decision_ts_ns, side)`
     — the decision timestamp is COLUMN 2 (`KEY_TS`), not column 3.

TRUTH STAYS BEHIND THE ALLOWLIST.  `features()` cannot resolve a truth leaf and
`truth()` is called with the frozen allowlist, so this module is the only place
a label is shaped and it holds no feature tensor while doing it.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import arms                                          # noqa: E402
from decision_tape_loader import DecisionTape        # noqa: E402

# --- the frozen spellings, read off the real manifest -----------------------

SIDES = ("L", "S")
SIDE_LONG, SIDE_SHORT = 0, 1

#: `keys [N,4] i8` column order, frozen in qr_replay/action.hpp's `ActionKey`.
KEY_SESSION, KEY_DECISION, KEY_TS, KEY_SIDE = 0, 1, 2, 3
#: ... and the side column carries SIGMA (+1 LONG, -1 SHORT), measured on the
#: emitted s0125 shards, not the 0/1 `Side` enum ordinal.
KEY_SIGMA = {"L": 1, "S": -1}

#: §4 channel counts; the stored group width is `4C+1+S`, the model's is `4C+1`.
CHANNELS = {"stock_print": 17, "stock_nbbo": 16, "option_print": 22}

#: `masks [N,7] u1`, frozen in qr_campaign/src/session_build.cpp: three watch
#: stage bits, three per-modality "the 120s window is nonempty" bits (this IS
#: the r_modality DIRECT column, copied, never recomputed), and legal_enter.
MASK_STAGE = slice(0, 3)
MASK_MODALITY = slice(3, 6)
MASK_LEGAL_ENTER = 6

#: qr_carriers/include/qr_carriers/channels.hpp `OrientKind`.
ORIENT_INVARIANT, ORIENT_SIGMA, ORIENT_SIGMA_RHO, ORIENT_SWAP = 0, 1, 2, 3

#: native_order.hpp `Phase`.
PHASE_APPROACH, PHASE_RESPONSE, PHASE_EQUAL = 0, 1, 2

#: §5's six latent checkpoints, seconds before the cutoff.
CHECKPOINT_OFFSETS_S = (60, 30, 15, 5, 1, 0)

TRUTH_ALLOWLIST = ("menu_net_cent", "cert_net_cent", "stop_hit", "barrier",
                   "label_state", "keys")


class TapeBindingError(Exception):
    """The tape does not carry what this loader was told it carries."""


def _refuse(message: str) -> None:
    raise TapeBindingError(message)


# --- the orientation law (native_emit.hpp, verbatim) ------------------------


def orient_group_vector(neutral: np.ndarray, orientation: np.ndarray,
                        channels: int, side: int) -> np.ndarray:
    """`[K, 4C+1+S] -> [K, 4C+1]` for one side.

    native_emit.hpp, verbatim: with `mean_value=[0,C)`, `mean_mask=[C,2C)`,
    `max_value=[2C,3C)`, `max_mask=[3C,4C)`, `log1p_multiplicity=4C` and
    `min_value=[4C+1,...)`,

      LONG  : take `groups[:, :4C+1]` verbatim (sigma = +1);
      SHORT : INVARIANT             -> copy the four cells;
              SIGMA / SIGMA_RHO     -> mean = -mean, max = -min_value[min_slot],
                                       masks copied, and an absent channel
                                       (max_mask == 0) stays exactly +0.0;
              OWN_OPPOSITE_SWAP     -> value AND mask from `partner`, in both
                                       the mean and the max block;
              log1p_multiplicity is side-invariant.
    """
    width = 4 * channels + 1
    if neutral.ndim != 2 or neutral.shape[1] < width:
        _refuse(f"group table is {neutral.shape}, needs at least {width} columns")
    if orientation.shape != (channels, 3):
        _refuse(f"orientation table is {orientation.shape}, expected ({channels},3)")
    out = np.array(neutral[:, :width], dtype=np.float32, copy=True)
    if side == SIDE_LONG:
        return out

    kind = orientation[:, 0]
    partner = orientation[:, 1]
    min_slot = orientation[:, 2]
    mean_value = neutral[:, 0:channels]
    mean_mask = neutral[:, channels:2 * channels]
    max_value = neutral[:, 2 * channels:3 * channels]
    max_mask = neutral[:, 3 * channels:4 * channels]
    min_value = neutral[:, width:]

    negates = np.flatnonzero((kind == ORIENT_SIGMA) | (kind == ORIENT_SIGMA_RHO))
    if negates.size:
        slots = min_slot[negates]
        if np.any(slots < 0) or np.any(slots >= min_value.shape[1]):
            _refuse("a negating channel has no slot in the min block")
        # mean negates; the SHORT max is the NEGATED MIN.
        out[:, negates] = -mean_value[:, negates]
        out[:, 2 * channels + negates] = -min_value[:, slots]
        # An ABSENT channel stays exactly +0.0 rather than becoming -0.0.
        absent = max_mask[:, negates] == 0
        block = out[:, 2 * channels + negates]
        block[absent] = 0.0
        out[:, 2 * channels + negates] = block
        mean_absent = mean_mask[:, negates] == 0
        block = out[:, negates]
        block[mean_absent] = 0.0
        out[:, negates] = block

    swaps = np.flatnonzero(kind == ORIENT_SWAP)
    if swaps.size:
        mates = partner[swaps]
        if np.any(mates < 0) or np.any(mates >= channels):
            _refuse("an OWN_OPPOSITE_SWAP channel has no partner")
        out[:, swaps] = mean_value[:, mates]
        out[:, channels + swaps] = mean_mask[:, mates]
        out[:, 2 * channels + swaps] = max_value[:, mates]
        out[:, 3 * channels + swaps] = max_mask[:, mates]
    return out


# --- the two carriers, from their emitted (start,len) forms -----------------


def expand_recent128(recent: np.ndarray) -> np.ndarray:
    """`recent128 [B,2] (start,len)` -> `[B,128]` group indices, -1 on left pad.

    native_order.hpp `MicroCarrier`: slot `i` holds a group index or -1 on a
    typed LEFT pad, and `left_pad = 128 - length`.
    """
    rows = recent.shape[0]
    width = arms.MICRO_LENGTH
    start = recent[:, 0].astype(np.int64)
    length = np.clip(recent[:, 1].astype(np.int64), 0, width)
    position = np.arange(width, dtype=np.int64)[None, :]
    left_pad = (width - length)[:, None]
    slot = start[:, None] + (position - left_pad)
    return np.where(position >= left_pad, slot, -1)


def phase_of(group_index: np.ndarray, phase_split: np.ndarray) -> np.ndarray:
    """native_order.hpp `PhaseSplit::phase_of`, vectorised over [B,K] indices.

    `phase_split [B,2] i4` is `(equal_lo, equal_hi)`, and `(-1,-1)` marks an
    ABSENT visibility reference, which types every group PHASE_EQUAL_UNORDERED.
    """
    equal_lo = phase_split[:, 0].astype(np.int64)[:, None]
    equal_hi = phase_split[:, 1].astype(np.int64)[:, None]
    present = equal_lo >= 0
    phase = np.full(group_index.shape, PHASE_EQUAL, dtype=np.int64)
    phase = np.where(present & (group_index < equal_lo), PHASE_APPROACH, phase)
    phase = np.where(present & (group_index >= equal_hi), PHASE_RESPONSE, phase)
    return np.where(group_index < 0, PHASE_EQUAL, phase)


def bin_segments(bins_index: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`bins_index [B,120,2] (start,len)` -> the shared per-second segment table.

    Measured on session 125: a bin is an absolute session-second segment and
    every row spanning that second carries the SAME (start,len).  So the bin is
    reduced once and referenced, which is what makes the real widths tractable.

    Returns `(seg_start [U], seg_len [U], bin_ref [B,120])`, with `bin_ref = -1`
    on a pre-open pad bin (`start < 0`).
    """
    start = bins_index[..., 0].astype(np.int64)
    length = bins_index[..., 1].astype(np.int64)
    valid = start >= 0
    bin_ref = np.full(start.shape, -1, dtype=np.int64)
    if not valid.any():
        return (np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), bin_ref)
    seg_start, inverse = np.unique(start[valid], return_inverse=True)
    seg_len = np.zeros(seg_start.shape[0], dtype=np.int64)
    seg_len[inverse] = length[valid]
    # The same second must not be described two different ways by two rows.
    check = np.zeros(seg_start.shape[0], dtype=np.int64)
    check[inverse] = length[valid]
    if not np.array_equal(check, seg_len):
        _refuse("two rows disagree about one second-bin's length")
    bin_ref[valid] = inverse
    return seg_start, seg_len, bin_ref


def _ranges_to_mask(mask: np.ndarray, start: np.ndarray, length: np.ndarray) -> None:
    """Marks `[start, start+length)` for every (start,length) pair, vectorised."""
    keep = (start >= 0) & (length > 0)
    start, length = start[keep], length[keep]
    if start.size == 0:
        return
    total = int(length.sum())
    offsets = np.repeat(np.cumsum(length) - length, length)
    index = np.repeat(start, length) + (np.arange(total, dtype=np.int64) - offsets)
    mask[index] = True


# --- one (session, side) ----------------------------------------------------


def _session_dir(root: pathlib.Path, ordinal: int, side: str) -> pathlib.Path:
    base = pathlib.Path(root)
    tapes = base / "tapes"
    if tapes.is_dir():
        base = tapes
    return base / f"s{ordinal:04d}" / side


def load_side(root: pathlib.Path, ordinal: int, side: str, *,
              verify_sha: bool = False, rows: np.ndarray | None = None,
              with_groups: bool = True):
    """Binds ONE published (session, side) tape to `(arms.Batch, Targets)`.

    The group table always comes from the LONG shard (side-neutral storage) and
    is oriented for `side` here.
    """
    import synth                                   # for Targets/build_targets

    if side not in SIDES:
        _refuse(f"{side!r} is not a side")
        return None
    tape = DecisionTape(_session_dir(root, ordinal, side), verify_sha=verify_sha)
    long_tape = (tape if side == "L"
                 else DecisionTape(_session_dir(root, ordinal, "L"),
                                   verify_sha=verify_sha))
    sigma = SIDE_LONG if side == "L" else SIDE_SHORT

    features = tape.features()
    # A non-native arm never reads a group table; mapping 753 MB of NBBO groups
    # for it would be the single most expensive thing the loader does.
    session_features = (long_tape.features(
        [f"{leaf}_{modality}" for modality in arms.MODALITIES
         for leaf in ("groups", "group_ts", "orientation")])
        if with_groups else {})

    keys = np.asarray(features["keys"])
    total_rows = keys.shape[0]
    index = (np.arange(total_rows, dtype=np.int64) if rows is None
             else np.asarray(rows, dtype=np.int64))
    if index.size and (index.min() < 0 or index.max() >= total_rows):
        _refuse("row selection is outside the tape")
    stored_sigma = np.unique(np.asarray(keys[:, KEY_SIDE]))
    if stored_sigma.size != 1 or int(stored_sigma[0]) != KEY_SIGMA[side]:
        _refuse(f"{side}: keys sigma column is {stored_sigma.tolist()}, "
                f"expected [{KEY_SIGMA[side]}]")

    masks = np.asarray(features["masks"])[index]
    cutoff_ns = keys[index, KEY_TS].astype(np.int64)

    groups: list[torch.Tensor] = []
    micro_slot, micro_phase, micro_ckpt = [], [], []
    bin_ref_all, bin_seg_all, bin_segment_count = [], [], []
    jsa_pool_ts, jsa_pool_slot, jsa_pool_phase, jsa_pool_mod = [], [], [], []

    for modality_index, modality in enumerate(arms.MODALITIES):
        channels = CHANNELS[modality]
        if not with_groups:
            groups.append(torch.zeros(1, 4 * channels + 1, dtype=torch.float32))
            # A non-native arm reads none of these, so they are kept at width 1
            # instead of the full 128/120 -- the row axis is all `slice_batch`
            # needs, and the difference is ~240 MB a side on a real session.
            micro_slot.append(np.full((index.size, 1), -1, dtype=np.int64))
            micro_phase.append(np.full((index.size, 1), PHASE_EQUAL, dtype=np.int64))
            micro_ckpt.append(np.full((index.size, len(CHECKPOINT_OFFSETS_S)), -1,
                                      dtype=np.int64))
            bin_ref_all.append(np.full((index.size, 1), -1, dtype=np.int64))
            bin_seg_all.append(np.full(1, -1, dtype=np.int64))
            bin_segment_count.append(1)
            jsa_pool_ts.append(np.full((index.size, 1), np.iinfo(np.int64).min))
            jsa_pool_slot.append(np.full((index.size, 1), -1, dtype=np.int64))
            jsa_pool_phase.append(np.full((index.size, 1), PHASE_EQUAL, dtype=np.int64))
            jsa_pool_mod.append(np.full((index.size, 1), modality_index, dtype=np.int64))
            continue
        neutral = session_features[f"groups_{modality}"]
        group_ts = np.asarray(session_features[f"group_ts_{modality}"])
        orientation = np.asarray(session_features[f"orientation_{modality}"])
        if neutral.shape[1] != 4 * channels + 1 + int((orientation[:, 0] == ORIENT_SIGMA).sum()
                                                      + (orientation[:, 0] == ORIENT_SIGMA_RHO).sum()):
            _refuse(f"groups_{modality} width {neutral.shape[1]} is not 4C+1+S")

        recent = np.asarray(features[f"recent128_{modality}"])[index]
        bins = np.asarray(features[f"bins_index_{modality}"])[index]
        split = np.asarray(features[f"phase_split_{modality}"])[index]

        slot = expand_recent128(recent)                       # [B,128]
        seg_start, seg_len, bin_ref = bin_segments(bins)      # [U],[U],[B,120]

        # Compact the session's group axis to what these rows actually touch:
        # the projection is per-group elementwise, so this is exact.
        touched = np.zeros(group_ts.shape[0], dtype=bool)
        _ranges_to_mask(touched, recent[:, 0].astype(np.int64),
                        np.clip(recent[:, 1].astype(np.int64), 0, arms.MICRO_LENGTH))
        _ranges_to_mask(touched, seg_start, seg_len)
        used = np.flatnonzero(touched)
        if used.size == 0:
            used = np.zeros(1, dtype=np.int64)

        oriented = orient_group_vector(np.asarray(neutral[used]), orientation,
                                       channels, sigma)
        groups.append(torch.from_numpy(oriented))

        remap = np.full(group_ts.shape[0], -1, dtype=np.int64)
        remap[used] = np.arange(used.size, dtype=np.int64)
        compact_slot = np.where(slot >= 0, remap[np.clip(slot, 0, None)], -1)
        if np.any((slot >= 0) & (compact_slot < 0)):
            _refuse(f"{modality}: a recent-128 slot fell outside the compaction")

        micro_slot.append(compact_slot)
        micro_phase.append(phase_of(slot, split))

        # Segment id of every compacted group, and the row->segment reference.
        seg_of_group = np.full(used.size, -1, dtype=np.int64)
        if seg_start.size:
            lows = np.searchsorted(used, seg_start)
            keep = seg_len > 0
            if keep.any():
                offsets = np.repeat(np.cumsum(seg_len[keep]) - seg_len[keep], seg_len[keep])
                positions = (np.repeat(lows[keep], seg_len[keep])
                             + np.arange(int(seg_len[keep].sum()), dtype=np.int64) - offsets)
                seg_of_group[positions] = np.repeat(np.flatnonzero(keep), seg_len[keep])
        bin_seg_all.append(seg_of_group)
        bin_ref_all.append(bin_ref)
        bin_segment_count.append(int(seg_start.size))

        # The JSA pool: the merged union is taken over the three recent-128
        # windows, which is sufficient because a group outside its own
        # modality's most-recent 128 cannot be inside the global most-recent 192.
        stamps = np.where(slot >= 0, group_ts[np.clip(slot, 0, None)], np.iinfo(np.int64).min)
        jsa_pool_ts.append(stamps)
        jsa_pool_slot.append(compact_slot)
        jsa_pool_phase.append(micro_phase[-1])
        jsa_pool_mod.append(np.full(slot.shape, modality_index, dtype=np.int64))

        # §5's six latent checkpoints: the LATEST retained slot at or before
        # cutoff - offset, or -1 when the window does not reach back that far.
        checkpoints = np.full((index.size, len(CHECKPOINT_OFFSETS_S)), -1, dtype=np.int64)
        for position, offset in enumerate(CHECKPOINT_OFFSETS_S):
            deadline = cutoff_ns - offset * 1_000_000_000
            eligible = (slot >= 0) & (stamps <= deadline[:, None])
            any_eligible = eligible.any(axis=1)
            latest = arms.MICRO_LENGTH - 1 - np.argmax(eligible[:, ::-1], axis=1)
            checkpoints[any_eligible, position] = latest[any_eligible]
        micro_ckpt.append(checkpoints)

    jsa_mod, jsa_slot, jsa_phase, jsa_ts_us = _merge_jsa(
        jsa_pool_ts, jsa_pool_slot, jsa_pool_phase, jsa_pool_mod)

    candset, candset_valid = _read_candset(features, index)
    location = np.asarray(features["locclock"])[index]

    batch = arms.Batch(
        candset=torch.from_numpy(candset),
        candset_valid=torch.from_numpy(candset_valid),
        loc_value=torch.from_numpy(np.ascontiguousarray(
            location[:, :arms.LOCATION_VALUES], dtype=np.float32)),
        loc_present=torch.from_numpy(np.ascontiguousarray(
            location[:, arms.LOCATION_VALUES:arms.LOCATION_INPUTS], dtype=np.float32)),
        visible_count=torch.from_numpy(candset_valid.sum(axis=1).astype(np.float32)),
        direct=torch.from_numpy(np.asarray(features["direct_raw"])[index].astype(np.float32)),
        r_modality=torch.from_numpy(masks[:, MASK_MODALITY].astype(np.float32)),
        groups=tuple(groups),
        micro_slot=torch.from_numpy(np.stack(micro_slot, axis=1)),
        micro_phase=torch.from_numpy(np.stack(micro_phase, axis=1)),
        micro_ckpt=torch.from_numpy(np.stack(micro_ckpt, axis=1)),
        bin_ref=torch.from_numpy(np.stack(bin_ref_all, axis=1)),
        bin_seg=tuple(torch.from_numpy(seg) for seg in bin_seg_all),
        bin_segments=tuple(bin_segment_count),
        jsa_mod=torch.from_numpy(jsa_mod),
        jsa_slot=torch.from_numpy(jsa_slot),
        jsa_phase=torch.from_numpy(jsa_phase),
        jsa_ts_us=torch.from_numpy(jsa_ts_us),
    )

    allowed = tape.truth(list(TRUTH_ALLOWLIST))
    stage_mask = np.zeros(index.size, dtype=np.int64)
    for bit in range(3):
        stage_mask |= (masks[:, bit].astype(np.int64) << bit)
    targets = synth.build_targets(
        menu_net_cent=np.asarray(allowed["menu_net_cent"])[index],
        cert_net_cent=np.asarray(allowed["cert_net_cent"])[index],
        stop_hit=np.asarray(allowed["stop_hit"])[index],
        barrier=np.asarray(allowed["barrier"])[index],
        label_state=np.asarray(allowed["label_state"])[index],
        keys=np.asarray(allowed["keys"])[index],
        stage_mask=stage_mask)
    return batch, targets


def _read_candset(features, index: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`candset [T,24]` + `candset_offsets [N+1]` (CSR) -> `[B,C,24]` + `[B,C]`."""
    offsets = np.asarray(features["candset_offsets"]).astype(np.int64)
    table = features["candset"]
    lo = offsets[index]
    hi = offsets[index + 1]
    counts = hi - lo
    capacity = int(counts.max()) if counts.size else 0
    capacity = max(capacity, 1)
    out = np.zeros((index.size, capacity, arms.CANDSET_FIELDS), dtype=np.float32)
    valid = np.zeros((index.size, capacity), dtype=np.float32)
    for position in range(index.size):
        count = int(counts[position])
        if count:
            out[position, :count] = table[lo[position]:hi[position]]
            valid[position, :count] = 1.0
    return out, valid


def _merge_jsa(pool_ts, pool_slot, pool_phase, pool_mod):
    """The §5 5b merged chronological union: the last M=192 tokens across the
    three modalities, ordered by (timestamp, modality, slot) so equal stamps
    have one stable order (the attention is permutation-invariant there)."""
    stamps = np.concatenate(pool_ts, axis=1)
    slots = np.concatenate(pool_slot, axis=1)
    phases = np.concatenate(pool_phase, axis=1)
    modalities = np.concatenate(pool_mod, axis=1)
    present = slots >= 0
    rows, width = stamps.shape
    tokens = arms.JSA_TOKENS

    order = np.lexsort((slots, modalities, stamps), axis=1)
    take = np.take_along_axis(present, order, axis=1)
    # Rank the present tokens from the most recent backwards; keep the last 192.
    reverse = take[:, ::-1]
    rank = np.cumsum(reverse, axis=1) - 1
    keep_reverse = reverse & (rank < tokens)
    keep = keep_reverse[:, ::-1]
    slot_sorted = np.take_along_axis(slots, order, axis=1)
    phase_sorted = np.take_along_axis(phases, order, axis=1)
    mod_sorted = np.take_along_axis(modalities, order, axis=1)
    ts_sorted = np.take_along_axis(stamps, order, axis=1)

    out_slot = np.full((rows, tokens), -1, dtype=np.int64)
    out_phase = np.full((rows, tokens), PHASE_EQUAL, dtype=np.int64)
    out_mod = np.full((rows, tokens), -1, dtype=np.int64)
    out_ts = np.zeros((rows, tokens), dtype=np.int64)
    kept = keep.sum(axis=1)
    column = np.arange(width, dtype=np.int64)[None, :]
    # Right-align: the newest token lands in the last column.
    destination = tokens - (kept[:, None] - np.cumsum(keep, axis=1)) - 1
    flat_rows = np.repeat(np.arange(rows, dtype=np.int64), kept)
    flat_dest = destination[keep]
    del column
    out_slot[flat_rows, flat_dest] = slot_sorted[keep]
    out_phase[flat_rows, flat_dest] = phase_sorted[keep]
    out_mod[flat_rows, flat_dest] = mod_sorted[keep]
    out_ts[flat_rows, flat_dest] = ts_sorted[keep] // 1000
    return out_mod, out_slot, out_phase, out_ts


def decision_ordinals(root: pathlib.Path, ordinal: int, side: str) -> np.ndarray:
    """The side's `decision_ordinal` column, mapped from the FEATURE `keys`
    leaf alone -- one small array, cheap enough to call per session before
    deciding which rows are worth assembling, and it touches no truth."""
    # Read from features/keys.npy, NOT truth/keys.npy.  The two carry the same
    # four columns (verified on s0125), but the decision ordinal used to CHOOSE
    # rows is a scientific key, not a label -- taking it from the truth section
    # would make a row selection depend on a truth read for no reason, and
    # check_truth_separation is right to object to that.
    tape = DecisionTape(_session_dir(root, ordinal, side))
    return np.array(np.asarray(tape.features(["keys"])["keys"])[:, KEY_DECISION],
                    copy=True)


def load_session(root: pathlib.Path, ordinal: int, *, verify_sha: bool = False,
                 rows: np.ndarray | None = None, with_groups: bool = True,
                 rows_by_side: dict | None = None) -> dict:
    """`rows_by_side` selects a DIFFERENT row subset per side, which is what the
    ranked training selection needs (a clock can be authorised on one side
    only)."""
    return {side: load_side(root, ordinal, side, verify_sha=verify_sha,
                            rows=(rows_by_side[side] if rows_by_side is not None
                                  else rows),
                            with_groups=with_groups)
            for side in SIDES}
