"""Frozen raw-price units used by corpus consumers."""

from types import MappingProxyType

SENTINEL_HIGH = 1 << 62
RAW_PRICE_SCALE = 1.0e-9
ASSET_MULTIPLIER = MappingProxyType({"SI": 5_000, "HG": 25_000, "NKD": 5})
ASSET_RAW_TICK = MappingProxyType(
    {
        "SI": 5_000_000,
        "HG": 500_000,
        "NKD": 5_000_000_000,
    }
)
