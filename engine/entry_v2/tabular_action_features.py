"""One label-free action-feature implementation shared by fit and runtime."""

from __future__ import annotations

import numpy as np

from . import common as C
from .tabular_recovery_contracts import (
    ACTIVE_WATCH_KEYS, COMPONENT_STACK_NAMES, REGIME_FEATURE_NAMES,
    RecoveryRefusal, validate_model_feature_names,
)


ACTION_STATE_FEATURE_NAMES = (
    "portfolio_entries_used",
    *(name for asset in C.ASSETS for name in (
        f"portfolio_{asset}_occupied", f"portfolio_{asset}_open_remaining_sec")),
    *(f"portfolio_active_{asset}_{'short' if side < 0 else 'long'}"
      for asset, side in ACTIVE_WATCH_KEYS),
    "portfolio_phase_index", "portfolio_receive_second_utc",
    *REGIME_FEATURE_NAMES,
)


def phase_number(value: object) -> float:
    text=str(value)
    try: return float(int(text))
    except ValueError:
        return float({"TOKYO":0,"LONDON":1,"NY":2}.get(text.upper(),-1))


def qrf4_regime_matrix(
    feature_names: tuple[str,...],matrix: np.ndarray,
) -> np.ndarray:
    names=validate_model_feature_names(feature_names)
    values=np.asarray(matrix,np.float32)
    if values.ndim!=2 or values.shape[1]!=len(names):
        raise RecoveryRefusal("QRF4 regime input matrix differs")
    aliases=("disc_fvol_phase_regime_low","disc_fvol_phase_regime_mid",
             "disc_fvol_phase_regime_high")
    positions={name:index for index,name in enumerate(names)}
    output=np.zeros((len(values),4),np.float32)
    selected=[positions.get(name) for name in aliases]
    if any(index is None for index in selected):
        output[:,3]=1;return output
    scores=values[:,np.asarray(selected,np.int64)];known=np.max(scores,axis=1)>0
    output[np.flatnonzero(known),np.argmax(scores[known],axis=1)]=1
    output[~known,3]=1;return output


def build_action_feature_matrix(*,causal_feature_names:tuple[str,...],
        causal_matrix:np.ndarray,component_predictions:np.ndarray,
        asset:np.ndarray,snapshot_ts_ns:np.ndarray,entries_used:np.ndarray,
        open_until_ts_ns:np.ndarray,active_watches_by_asset_side:np.ndarray,
        phase:np.ndarray)->tuple[tuple[str,...],np.ndarray]:
    names=validate_model_feature_names(causal_feature_names)
    causal=np.asarray(causal_matrix,np.float32);component=np.asarray(component_predictions,np.float32)
    assets=np.asarray(asset,str);timestamps=np.asarray(snapshot_ts_ns,np.int64)
    entries=np.asarray(entries_used,np.float32);opened=np.asarray(open_until_ts_ns,np.int64)
    active=np.asarray(active_watches_by_asset_side,np.float32);phases=np.asarray(phase,str)
    n=len(causal)
    if (causal.shape!=(n,len(names)) or component.shape!=(n,len(COMPONENT_STACK_NAMES))
            or any(value.shape!=(n,) for value in (assets,timestamps,entries,phases))
            or opened.shape!=(n,len(C.ASSETS))
            or active.shape!=(n,len(ACTIVE_WATCH_KEYS))
            or not np.all(np.isin(assets,C.ASSETS))
            or np.any(entries<0) or np.any(entries>C.MAX_ENTRIES_PORTFOLIO_DAY)
            or np.any(opened<-1) or np.any(active<0)
            or not np.all(np.isfinite(causal)) or not np.all(np.isfinite(component))):
        raise RecoveryRefusal("action feature inputs are malformed")
    columns=[entries]
    for asset_position,_asset in enumerate(C.ASSETS):
        remaining=np.maximum(0.0,(opened[:,asset_position]-timestamps)/1e9)
        columns.extend(((opened[:,asset_position]>=timestamps).astype(np.float32),
                        remaining.astype(np.float32)))
    columns.extend(active[:,index] for index in range(active.shape[1]))
    columns.append(np.asarray([phase_number(value) for value in phases],np.float32))
    columns.append(((timestamps//1_000_000_000)%86_400).astype(np.float32))
    regimes=qrf4_regime_matrix(names,causal)
    columns.extend(regimes[:,index] for index in range(regimes.shape[1]))
    state=np.column_stack(columns).astype(np.float32)
    output=np.column_stack((causal,component,state)).astype(np.float32)
    output_names=names+COMPONENT_STACK_NAMES+tuple(ACTION_STATE_FEATURE_NAMES)
    if output.shape!=(n,len(output_names)):
        raise RecoveryRefusal("action feature output schema differs")
    return output_names,output


__all__=["ACTION_STATE_FEATURE_NAMES","build_action_feature_matrix",
         "phase_number","qrf4_regime_matrix"]
