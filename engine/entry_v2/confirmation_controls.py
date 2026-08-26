"""Null shuffle and registered feature-family ablations."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal


def shuffle_confirmation_targets(
    dataset: ConfirmationDataset, seed: int,
) -> ConfirmationDataset:
    """Recipient-fixed, series-level target shuffle for the null learner."""

    dataset.validate()
    rng = np.random.default_rng(int(seed))
    series = np.asarray(dataset.series_id, str)
    assets = np.asarray(dataset.asset, str)
    target_fields = ("cert_close_usd", "mfe_usd", "mae_usd", "wall_hit")
    shuffled = {name: np.asarray(getattr(dataset, name)).copy()
                for name in target_fields}
    mapping: list[tuple[str, str]] = []
    for asset in sorted(set(assets)):
        recipients = sorted(set(series[assets == asset]))
        if len(recipients) < 2:
            raise ConfirmationRefusal(
                f"shuffle control needs at least two {asset} series")
        order = np.asarray(recipients, object)
        offset = int(rng.integers(1, len(order)))
        donors = np.roll(order[rng.permutation(len(order))], offset)
        # Repair accidental fixed points deterministically with a cyclic shift.
        if any(a == b for a, b in zip(order, donors)):
            donors = np.roll(order, offset)
        for recipient, donor in zip(order.tolist(), donors.tolist()):
            r_idx = np.flatnonzero(series == recipient)
            d_idx = np.flatnonzero(series == donor)
            r_idx = r_idx[np.argsort(dataset.snapshot_ts_ns[r_idx])]
            d_idx = d_idx[np.argsort(dataset.snapshot_ts_ns[d_idx])]
            donor_position = np.rint(np.linspace(
                0, len(d_idx) - 1, len(r_idx))).astype(np.int64)
            for name in target_fields:
                shuffled[name][r_idx] = np.asarray(
                    getattr(dataset, name))[d_idx[donor_position]]
            mapping.append((recipient, donor))
    receipt = C.object_sha256({
        "schema": "QRE2CONFSHUF1", "source": dataset.representation_sha256,
        "seed": int(seed), "mapping": mapping,
    })
    result = replace(
        dataset, **shuffled,
        source_receipts=dataset.source_receipts + (receipt,))
    result.validate()
    return result


def registered_feature_ablations(
    feature_names: Sequence[str],
) -> Mapping[str, np.ndarray]:
    """Masks that remove one interpretable discretion family at a time."""

    names = np.asarray(tuple(feature_names), str)
    tokens = MappingProxyType({
        "formation_reclaim": ("from_formation", "excursion"),
        "aggressive_flow": ("trade_flow", "flow_fraction", "buy_volume",
                            "sell_volume", "price_per_aligned_volume"),
        "absorption": ("absorption", "through_ask", "through_bid"),
        "defense_retreat": ("reload", "retreat", "book_size_change"),
        "path_shape": ("path_variation", "path_efficiency",
                       "mid_direction_balance"),
        "auction_location": ("disc_auction_",),
        "initial_balance": ("disc_ib_",),
        "level_memory": ("disc_memory_",),
        "price_local_control": ("disc_level_", "disc_current_"),
        "confirmation_state": ("disc_state_",),
        "forward_vol_state": ("disc_fvol_",),
        "event_micro_timing": ("disc_evt_", "disc_mhi_"),
        "adaptive_clocks": ("disc_eclock_", "disc_tclock_",
                            "disc_vclock_", "disc_tape_"),
        "repeated_test_state": ("disc_test_",),
        "best_quote_state": ("disc_quote_",),
        "behavior_interactions": ("disc_behavior_",),
        "footprint_shape": ("disc_footprint_",),
        "origin_reaction": ("disc_origin_",),
        "target_path": ("disc_target_",),
        "ordered_paths": ("disc_path_",),
        "regime_state": ("disc_regime_",),
        "prior_session_memory": ("disc_prior_",),
        "slow_context": ("ctx_",),
        "negative_control_markers": (
            "association_destroyed", "coupling_destroyed"),
    })
    output = {}
    for family, needles in tokens.items():
        keep = np.asarray([not any(token in name for token in needles)
                           for name in names], bool)
        if keep.all() and family in {
                "auction_location", "level_memory", "price_local_control",
                "confirmation_state", "forward_vol_state",
                "event_micro_timing", "footprint_shape", "origin_reaction",
                "target_path", "prior_session_memory", "initial_balance",
                "adaptive_clocks", "repeated_test_state", "best_quote_state",
                "behavior_interactions", "ordered_paths", "regime_state",
                "slow_context", "negative_control_markers"}:
            # Legacy cached/synthetic schemas predate these registered
            # families.  New production-path datasets must expose them, while
            # old regression fixtures remain loadable.
            continue
        if keep.all() or not keep.any():
            raise ConfirmationRefusal(f"feature ablation {family} is ineffective")
        output[family] = keep
    return MappingProxyType(output)
