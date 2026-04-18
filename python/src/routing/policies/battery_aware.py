from ..context import RoutingContext
from ..actions import RoutingAction
from ..policy import RoutingPolicy


class BatteryAwarePolicy(RoutingPolicy):
    def __init__(
        self,
        low_battery_threshold: float = 20.0,
        critical_battery_threshold: float = 5.0,
        confidence_threshold: float = 0.7,
    ):
        self._low_threshold = low_battery_threshold
        self._critical_threshold = critical_battery_threshold
        self._confidence_threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "battery_aware"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {
            "confidence": context.confidence,
            "battery_pct": context.battery_pct / 100.0,
        }

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        battery_pct = scores["battery_pct"] * 100.0
        confidence = scores["confidence"]

        if battery_pct <= self._critical_threshold:
            return RoutingAction.LOCAL

        if battery_pct <= self._low_threshold:
            return RoutingAction.LOCAL

        if confidence >= self._confidence_threshold:
            return RoutingAction.LOCAL

        return RoutingAction.CLOUD
