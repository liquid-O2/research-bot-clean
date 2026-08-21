"""Per-head CatBoost fit backend authority for the Entry V2 tabular recovery.

Law: D-105 (DIRECTIVES.md) amends the never-mix backend rule from
one-backend-per-TRANSITION to one-backend-per-HEAD. Every arm of a head (all
5 real + 5 matched-shuffle seeds, both rehearsal transitions) fits on ONE
backend; different heads may use different backends. MultiQuantile heads fit
CPU because catboost 1.2.10 has no GPU MultiQuantile implementation (DP-1
probe receipt gpu_loss_probe_20260821.json); the other five loss families fit
GPU. Every gated comparison (shuffle-must-fail, weakest-real >
strongest-shuffle) is within-head, so the split never crosses a comparison.

Determinism: DP-2 (receipt gpu_fit_determinism_20260821.json) selected mode
ARTIFACT_PIN — GPU fits are not bitwise reproducible, so each fit runs ONCE
and the published model artifact hash is the identity. That mode is recorded
for CPU heads too, because the receipt's own rationale states the .cbm hash
"can never repeat, on GPU or CPU" (CatBoost stamps a fresh model_guid and
train_finish_time into every fit).

This module holds NO fit code and NO frozen hyper-parameters. It maps a
CatBoost loss string to (a) its lawful backend, (b) the exact pinned
parameters a GPU head adds on top of tabular_models._common_parameters, and
(c) the fields every fit receipt must carry so a reader can tell which
backend produced the artifact.
"""

from __future__ import annotations

import subprocess
from types import MappingProxyType
from typing import Final, Mapping

from .tabular_recovery_contracts import RecoveryRefusal

CATBOOST_CPU: Final = "CATBOOST_CPU"
CATBOOST_GPU: Final = "CATBOOST_GPU"

# D-105, keyed by loss FAMILY (the token before the ':' in a CatBoost loss
# string). MultiQuantile -> CPU; the five named families -> GPU.
FIT_BACKEND_BY_LOSS_FAMILY: Final[Mapping[str, str]] = MappingProxyType({
    "MultiQuantile": CATBOOST_CPU,
    # Flipped GPU->CPU 2026-08-21 by the pre-registered big-fold probe
    # (gpu_quantile_bigfold_probe.json, verdict GPU_DEGENERATE: GPU 1 tree vs
    # CPU 5 on BURN_E2_STACK; both backends early-stop at 1 tree on
    # FROZEN_Q3_E8). D-105 amendment clause: GPU_DEGENERATE flips this head
    # to CPU before any of its E2R arms fit.
    "Quantile": CATBOOST_CPU,
    "Logloss": CATBOOST_GPU,
    "MultiRMSE": CATBOOST_GPU,
    "MultiClass": CATBOOST_GPU,
    "PairLogitPairwise": CATBOOST_GPU,
})

# The loss each component head fits, keyed by tabular_models.COMPONENT_FILES
# head name. Note `continuation`: D-105 enumerates "current, occupancy" as the
# MultiQuantile heads, but the fit code has a THIRD MultiQuantile head
# (tabular_models.py:397-398). Family routing sends it to CPU, which is the
# only lawful resolution — catboost 1.2.10 has no GPU MultiQuantile at all.
COMPONENT_HEAD_LOSS_FUNCTIONS: Final[Mapping[str, str]] = MappingProxyType({
    "current": "MultiQuantile:alpha=0.2,0.5,0.8",
    "continuation": "MultiQuantile:alpha=0.2,0.5,0.8",
    "wall": "Logloss",
    "adverse": "Quantile:alpha=0.9",
    "occupancy": "MultiQuantile:alpha=0.5,0.9",
})

# For an action bundle the objective string IS the loss string
# (ActionModelBundle.objective), so no separate map is needed.
ACTION_OBJECTIVE_LOSS_FUNCTIONS: Final = (
    "MultiRMSE", "MultiClass", "PairLogitPairwise")

# Every loss string the production fit code constructs today; the paired test
# re-derives this set from tabular_models.py so a new head cannot reach a fit
# without a D-105 backend ruling.
PRODUCTION_LOSS_FUNCTIONS: Final = tuple(dict.fromkeys(
    tuple(COMPONENT_HEAD_LOSS_FUNCTIONS.values())
    + ACTION_OBJECTIVE_LOSS_FUNCTIONS))

# The only non-semantic GPU knobs permitted beyond the frozen config (DP-2).
GPU_DEVICE_PARAMETERS: Final[Mapping[str, str]] = MappingProxyType({
    "task_type": "GPU", "devices": "0"})

# Orchestrator ruling recorded in the DP-2 receipt's
# deviations_requiring_ruling: CatBoost GPU defaults boosting_type=Ordered for
# MultiRMSE and then refuses ("Only plain boosting is supported in current
# mode"). CPU resolves the same unit to Plain, so Plain keeps the GPU arm on
# the published algorithm. Pinned, and stated in the fit receipt.
GPU_PLAIN_BOOSTING_LOSS_FAMILIES: Final = frozenset({"MultiRMSE"})

# Named REFERENCES, not assertions: these name the environment the DP-2
# determinism verdict was taken in. The environment a fit actually ran in is
# observed live (observed_catboost_version / observed_driver_version) and is
# recorded beside them, so a reader can see drift instead of inheriting a
# constant. Neither is an equality-gate field (FIT_RECEIPT_LAW_FIELDS).
DP2_CATBOOST_VERSION: Final = "1.2.10"
DP2_DRIVER_VERSION: Final = "580.126.16"
DP2_DETERMINISM_MODE: Final = "ARTIFACT_PIN"
DP2_DETERMINISM_RECEIPT: Final = "gpu_fit_determinism_20260821.json"

# The two heads DP-2 actually measured (receipt heads
# component_adverse_quantile_q90 and action_multirmse_regret). Every other head
# inherits the MODE by ruling, not by measurement, and says so in its receipt.
DP2_MEASURED_LOSS_FUNCTIONS: Final = frozenset(
    {"Quantile:alpha=0.9", "MultiRMSE"})

# The ONLY fields the §B3 strict-reload equality gate compares. Anything
# observed at fit time (versions, drivers) is deliberately outside this set: a
# driver upgrade between two arms is a fact to read, not a reload refusal.
FIT_RECEIPT_LAW_FIELDS: Final[tuple[str, ...]] = (
    "fit_backend", "task_type", "devices", "boosting_type",
    "determinism_mode", "determinism_receipt")


def _loss_family(loss_function: str) -> str:
    """The routing key: the token before the first ':' of a loss string."""

    if not isinstance(loss_function, str):
        raise RecoveryRefusal(
            f"fit backend needs a CatBoost loss string, got "
            f"{loss_function!r} ({type(loss_function).__name__}); expected one "
            f"of {sorted(FIT_BACKEND_BY_LOSS_FAMILY)}")
    family, separator, parameters = loss_function.partition(":")
    if separator and not parameters:
        raise RecoveryRefusal(
            f"malformed CatBoost loss string {loss_function!r}: a ':' with no "
            f"parameters; expected one of "
            f"{sorted(FIT_BACKEND_BY_LOSS_FAMILY)} with its alphas")
    return family


def fit_backend_for_loss(loss_function: str) -> str:
    """D-105 backend for one head, named by its CatBoost loss string."""

    family = _loss_family(loss_function)
    backend = FIT_BACKEND_BY_LOSS_FAMILY.get(family)
    if backend is None:
        raise RecoveryRefusal(
            f"no D-105 fit backend for loss {loss_function!r} (family "
            f"{family!r}); expected one of "
            f"{sorted(FIT_BACKEND_BY_LOSS_FAMILY)}")
    return backend


def gpu_fit_param_overlay(loss_function: str) -> dict[str, object]:
    """Pinned parameters this head adds to _common_parameters, or {} on CPU.

    Empty for CPU heads by design: a call site may merge the overlay
    unconditionally, so a MultiQuantile head receives no GPU parameter at all.
    """

    if fit_backend_for_loss(loss_function) != CATBOOST_GPU:
        return {}
    overlay: dict[str, object] = dict(GPU_DEVICE_PARAMETERS)
    if _loss_family(loss_function) in GPU_PLAIN_BOOSTING_LOSS_FAMILIES:
        overlay["boosting_type"] = "Plain"
    return overlay


def fit_receipt_law_fields(loss_function: str) -> dict[str, object]:
    """The D-105/DP-2 law half of a fit receipt: the §B3 equality-gate fields.

    Exactly FIT_RECEIPT_LAW_FIELDS, all of them pure functions of the loss
    string, so every arm of a head reproduces the identical dict by
    construction (arm symmetry, law-F9).
    """

    backend = fit_backend_for_loss(loss_function)
    overlay = gpu_fit_param_overlay(loss_function)
    return {
        "fit_backend": backend,
        "task_type": "GPU" if backend == CATBOOST_GPU else "CPU",
        "devices": overlay.get("devices"),
        "boosting_type": overlay.get("boosting_type"),
        "determinism_mode": DP2_DETERMINISM_MODE,
        "determinism_receipt": DP2_DETERMINISM_RECEIPT,
    }


def observed_catboost_version() -> str:
    """The catboost this process actually imported, read at fit time.

    Imported inside the function so this law module stays importable (and
    cheap) without the fit stack.
    """

    import catboost

    return str(catboost.__version__)


def observed_driver_version() -> str | None:
    """The NVIDIA driver nvidia-smi reports right now, or None if unreadable.

    None is a legitimate observation (no nvidia-smi on the box), never a gate
    failure: the driver is ENVIRONMENT, outside FIT_RECEIPT_LAW_FIELDS.
    """

    try:
        query = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    driver = query.stdout.strip().splitlines()[0].strip() if query.stdout else ""
    return driver or None


def fit_receipt_environment_fields(loss_function: str) -> dict[str, object]:
    """The observed half of a fit receipt: never compared, always readable."""

    is_gpu = fit_backend_for_loss(loss_function) == CATBOOST_GPU
    return {
        "catboost_version": observed_catboost_version(),
        "driver_version": observed_driver_version() if is_gpu else None,
        "dp2_reference_catboost": DP2_CATBOOST_VERSION,
        "dp2_reference_driver": DP2_DRIVER_VERSION,
        "determinism_head_measured":
            loss_function in DP2_MEASURED_LOSS_FUNCTIONS,
    }


def fit_receipt_backend_fields(loss_function: str) -> dict[str, object]:
    """What every fit receipt states about the backend that produced it.

    Split so the reader (and §B3) can tell law from observation: `law` is the
    equality gate, `environment` is context that may legitimately drift.
    """

    return {
        "loss_function": loss_function,
        "law": fit_receipt_law_fields(loss_function),
        "environment": fit_receipt_environment_fields(loss_function),
    }
