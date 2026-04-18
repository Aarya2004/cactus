from ..context import RoutingContext
from ..actions import RoutingAction
from ..policy import RoutingPolicy


class ThresholdPolicy(RoutingPolicy):
    def __init__(self, confidence_threshold: float = 0.7):
        self._threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "threshold"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {"confidence": context.confidence}

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["confidence"] >= self._threshold:
            return RoutingAction.LOCAL
        return RoutingAction.CLOUD
