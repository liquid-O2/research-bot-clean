"""Shared CatBoost fitting helpers for Entry V2 tabular models."""

from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

from catboost import Pool
import numpy as np

from . import common as C
from .tabular_fit_backends import gpu_fit_param_overlay
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal

def catboost_predict_threads() -> int:
    """Native threads for CatBoost predict. Corpus workers set this to 1.

    CatBoost ignores threadpoolctl. Default predict(thread_count=-1) takes
    every advertised core per process, so 16 workers become ~16×64 threads.
    """

    raw=os.environ.get("ENTRY_V2_PREDICT_THREADS","").strip()
    if raw.isdigit():
        return max(1,min(int(raw),C.MAX_CPU_WORKERS))
    return int(C.MAX_CPU_WORKERS)


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _config_from_json(value: Mapping[str, object]) -> RecoveryConfig:
    payload = dict(value)
    payload["real_seeds"] = tuple(map(int, payload["real_seeds"]))
    payload["shuffle_seeds"] = tuple(map(int, payload["shuffle_seeds"]))
    return RecoveryConfig(**payload)


def _assert_chronological(
    train_day: np.ndarray, validation_day: np.ndarray,
) -> None:
    left = np.asarray(train_day, np.int64); right = np.asarray(validation_day, np.int64)
    if (not len(left) or not len(right) or int(left.max()) >= int(right.min())
            or set(left.tolist()) & set(right.tolist())):
        raise RecoveryRefusal("CatBoost validation is not strictly chronological")


def _common_parameters(config: RecoveryConfig, seed: int) -> dict[str, object]:
    config.__post_init__()
    if seed not in config.real_seeds:
        raise RecoveryRefusal("CatBoost seed is outside the five frozen real seeds")
    return {
        "iterations": config.max_iterations,
        "depth": config.depth,
        "learning_rate": config.learning_rate,
        "l2_leaf_reg": config.l2_leaf_reg,
        "random_seed": int(seed),
        "thread_count": config.workers,
        "allow_writing_files": False,
        "verbose": False,
        "random_strength": 1.0,
    }


def _fit_with_early_stop(
    model: object, x: np.ndarray, y: np.ndarray, weight: np.ndarray,
    vx: np.ndarray, vy: np.ndarray, vweight: np.ndarray,
    *, patience: int,
) -> None:
    train_pool = Pool(x, label=y, weight=weight)
    validation_pool = Pool(vx, label=vy, weight=vweight)
    model.fit(
        train_pool, eval_set=validation_pool, use_best_model=True,
        early_stopping_rounds=patience)
    if int(model.tree_count_) <= 0:
        raise RecoveryRefusal("CatBoost fitted no trees")


def _head_model(factory, *, loss_function: str,
                common: Mapping[str, object]) -> object:
    """One CatBoost head: frozen parameters plus its D-105 GPU overlay.

    The overlay is {} for a CPU head (MultiQuantile), so this call is safe to
    use for every head; the backend is a pure function of the loss string.
    """

    return factory(loss_function=loss_function,
                   **{**common, **gpu_fit_param_overlay(loss_function)})


@contextmanager
def _bounded_row_subset(x:np.ndarray,selected:np.ndarray):
    """Expose selected feature rows without an unbounded advanced-index copy."""

    source=np.asarray(x,np.float32);keep=np.asarray(selected,bool)
    if keep.shape!=(len(source),) or not keep.any():
        raise RecoveryRefusal("CatBoost feature subset is empty/malformed")
    positions=np.flatnonzero(keep)
    if np.array_equal(positions,np.arange(positions[0],positions[-1]+1)):
        yield source[int(positions[0]):int(positions[-1])+1];return
    stage=Path(tempfile.mkdtemp(prefix="entry-v2-row-subset-"))
    mapping=None
    try:
        mapping=np.lib.format.open_memmap(stage/"x.npy",mode="w+",
            dtype=np.float32,shape=(len(positions),source.shape[1]))
        rows=max(1,4_000_000//max(1,source.shape[1]));cursor=0
        for start in range(0,len(source),rows):
            local=keep[start:start+rows]
            if not local.any():continue
            block=source[start:start+rows][local];end=cursor+len(block)
            mapping[cursor:end]=block;cursor=end
        if cursor!=len(mapping):
            raise RecoveryRefusal("CatBoost feature subset row count differs")
        mapping.flush();yield mapping
    finally:
        if mapping is not None:
            raw=getattr(mapping,"_mmap",None)
            if raw is not None:raw.close()
        shutil.rmtree(stage,ignore_errors=True)


def _serialized_model_sha256(model:object)->str:
    """Hash the exact CBM bytes used by receipts before publication."""

    descriptor,path=tempfile.mkstemp(prefix="entry-v2-tabular-",suffix=".cbm")
    os.close(descriptor)
    try:
        model.save_model(path,format="cbm")
        return C.file_sha256(path)
    finally:
        try:os.unlink(path)
        except FileNotFoundError:pass


def _fixed_fit(model:object,x:np.ndarray,y:np.ndarray,
               weight:np.ndarray)->None:
    model.fit(Pool(np.asarray(x,np.float32),label=np.asarray(y),
                   weight=np.asarray(weight,np.float64)))
    if int(model.tree_count_)<=0:
        raise RecoveryRefusal("all-data refit produced no trees")

