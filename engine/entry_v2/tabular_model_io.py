"""Strict model dispatch shared by training, replay, and publication.

The primary learner remains CatBoost.  The failure ladder may replace the
learner backend without changing the feature, policy, replay, or chronology
interfaces, so callers must never infer a model type from a directory name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from . import common as C
from .tabular_fallbacks import (
    HISTOGRAM_ACTION_SCHEMA,HISTOGRAM_COMPONENT_SCHEMA,
    HistogramActionBundle,HistogramComponentBundle,
)
from .tabular_models import (
    ACTION_MODEL_SCHEMA,COMPONENT_MODEL_SCHEMA,
    ActionModelBundle,ComponentModelBundle,
)
from .tabular_recovery_contracts import RecoveryRefusal


def _schema(path:str|Path)->str:
    source=Path(path).resolve();C.guard_payload(source)
    try:value=json.loads((source/"manifest.json").read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot inspect tabular model manifest") from exc
    schema=value.get("schema")
    if not isinstance(schema,str):
        raise RecoveryRefusal("tabular model manifest has no schema")
    return schema


def load_component_model(path:str|Path)->ComponentModelBundle|HistogramComponentBundle:
    schema=_schema(path)
    if schema==COMPONENT_MODEL_SCHEMA:return ComponentModelBundle.load(path)
    if schema==HISTOGRAM_COMPONENT_SCHEMA:return HistogramComponentBundle.load(path)
    raise RecoveryRefusal("component model backend is unregistered")


def load_action_model(path:str|Path)->Any:
    schema=_schema(path)
    if schema==ACTION_MODEL_SCHEMA:return ActionModelBundle.load(path)
    if schema==HISTOGRAM_ACTION_SCHEMA:return HistogramActionBundle.load(path)
    # Causal expert ensembles register their loader lazily to avoid a circular
    # dependency while this module remains the sole runtime dispatch point.
    from .tabular_fallbacks import CAUSAL_EXPERT_SCHEMA,CausalExpertActionEnsemble
    if schema==CAUSAL_EXPERT_SCHEMA:return CausalExpertActionEnsemble.load(path)
    raise RecoveryRefusal("action model backend is unregistered")


def predict_action_regret(model:Any,x:np.ndarray,*,trading_day:int)->np.ndarray:
    """Invoke a fixed model or a strictly-prior day-routed expert."""

    C.guard_date(int(trading_day))
    if getattr(model,"day_routed",False):
        return np.asarray(model.predict_regret_usd(x,trading_day=trading_day),np.float64)
    return np.asarray(model.predict_regret_usd(x),np.float64)


__all__=["load_action_model","load_component_model","predict_action_regret"]
