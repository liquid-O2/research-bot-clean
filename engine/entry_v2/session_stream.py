#!/usr/bin/env python3
"""Bounded, receipt-bearing materialization of one QRE2 asset-session.

``SessionEventSource`` is an immutable reference, not a cache.  It carries the
externally trusted identity of one QRE2 event pack and opens that pack only
inside a context manager.  Every identity check completes before
``EventPack.model_arrays`` is called, only rows ``[0, max_cutoff)`` are
converted, and the underlying memory map is closed on every exit path.

The deterministic receipt binds the full source hash to the exact event-byte
interval consumed by the model conversion.  It also names the conversion law
instead of treating a pair of anonymous NumPy arrays as sufficient lineage.
No module-level collection retains a source, pack, array, or batch.
"""

from .event_pack import EventPack as EventPack
from .session_cache import SessionArrayCache
from .session_receipt import (
    CUTOFF_RULE,
    MODEL_ARRAYS_CONVERSION_LAW,
    MODEL_ARRAYS_CONVERSION_LAW_SHA256,
    SESSION_STREAM_RECEIPT_SCHEMA,
    SessionSourceMeasurements,
    SessionStreamReceipt,
)
from .session_source import SessionEventSource

__all__ = [
    "CUTOFF_RULE",
    "MODEL_ARRAYS_CONVERSION_LAW",
    "MODEL_ARRAYS_CONVERSION_LAW_SHA256",
    "SESSION_STREAM_RECEIPT_SCHEMA",
    "SessionArrayCache",
    "SessionEventSource",
    "SessionSourceMeasurements",
    "SessionStreamReceipt",
]
