"""Stable imports for Entry V2 CatBoost model bundles."""

from .tabular_fit_backends import PRODUCTION_LOSS_FUNCTIONS
from .tabular_model_action import (
    ACTION_MODEL_SCHEMA, ActionModelBundle, _pairwise_pool, fit_action_bundle,
    fit_all_pre_h2_action_bundle, fit_pairwise_action_bundle,
)
from .tabular_model_component import (
    COMPONENT_FILES, COMPONENT_MODEL_SCHEMA, ComponentArrayPredictions,
    ComponentModelBundle, fit_all_pre_h2_component_bundle,
    fit_component_bundle,
)
from .tabular_model_fit import (
    _bounded_row_subset, _common_parameters, _config_from_json,
    _fit_with_early_stop, catboost_predict_threads,
)


def _declared_loss(*, loss_function: str) -> str:
    return loss_function


_FACADE_PRODUCTION_LOSSES = frozenset({
    _declared_loss(loss_function="MultiQuantile:alpha=0.2,0.5,0.8"),
    _declared_loss(loss_function="MultiQuantile:alpha=0.5,0.9"),
    _declared_loss(loss_function="Quantile:alpha=0.9"),
    _declared_loss(loss_function="Logloss"),
    _declared_loss(loss_function="MultiRMSE"),
    _declared_loss(loss_function="MultiClass"),
    _declared_loss(loss_function="PairLogitPairwise"),
})
if _FACADE_PRODUCTION_LOSSES != frozenset(PRODUCTION_LOSS_FUNCTIONS):
    raise RuntimeError("tabular model facade loss roster differs")


__all__ = [
    "ACTION_MODEL_SCHEMA", "COMPONENT_MODEL_SCHEMA", "ActionModelBundle",
    "ComponentArrayPredictions", "ComponentModelBundle", "fit_action_bundle",
    "fit_all_pre_h2_action_bundle", "fit_all_pre_h2_component_bundle",
    "fit_component_bundle", "fit_pairwise_action_bundle",
]
