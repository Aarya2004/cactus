from typing import Optional

from ..context import RoutingContext
from ..actions import RoutingAction
from ..policy import RoutingPolicy


class ThresholdPolicy(RoutingPolicy):
    """Confidence-threshold routing matching the engine's cloud-handoff gate.

    When ``confidence_threshold`` is ``None``, the policy defers to the model's
    per-model default, read from ``context.metadata['model_default_confidence_threshold']``.
    This mirrors the engine behavior in ``cactus_complete.cpp`` where an unset
    threshold falls back to ``default_cloud_handoff_threshold`` from model config,
    and finally to 0.7 if neither is available.
    """

    _FALLBACK_THRESHOLD = 0.7

    def __init__(self, confidence_threshold: Optional[float] = 0.7):
        self._threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "threshold"

    def score(self, context: RoutingContext) -> dict[str, float]:
        if self._threshold is not None:
            effective = self._threshold
        else:
            model_default = context.metadata.get("model_default_confidence_threshold")
            effective = (
                float(model_default)
                if isinstance(model_default, (int, float)) and model_default > 0.0
                else self._FALLBACK_THRESHOLD
            )

        return {
            "confidence": context.confidence,
            "effective_threshold": effective,
        }

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["confidence"] >= scores["effective_threshold"]:
            return RoutingAction.LOCAL
        return RoutingAction.CLOUD
