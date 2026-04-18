from ..context import RoutingContext
from ..actions import RoutingAction
from ..policy import RoutingPolicy

NETWORK_LATENCY_ESTIMATES_MS = {
    "fast": 50,
    "slow": 500,
    "offline": float("inf"),
}


class LatencyBudgetPolicy(RoutingPolicy):
    def __init__(
        self,
        local_latency_ms: int = 100,
        confidence_threshold: float = 0.7,
    ):
        self._local_latency_ms = local_latency_ms
        self._confidence_threshold = confidence_threshold

    @property
    def name(self) -> str:
        return "latency_budget"

    def score(self, context: RoutingContext) -> dict[str, float]:
        network_latency = NETWORK_LATENCY_ESTIMATES_MS.get(
            context.network_quality, 200
        )

        if context.latency_budget_ms <= 0:
            latency_pressure = 1.0
        else:
            latency_pressure = min(
                1.0, network_latency / context.latency_budget_ms
            )

        network_score = 1.0 if context.network_quality == "fast" else (
            0.5 if context.network_quality == "slow" else 0.0
        )

        return {
            "confidence": context.confidence,
            "latency_pressure": latency_pressure,
            "network_score": network_score,
        }

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["network_score"] == 0.0:
            return RoutingAction.LOCAL

        if scores["latency_pressure"] >= 0.8:
            return RoutingAction.LOCAL

        if scores["confidence"] >= self._confidence_threshold:
            return RoutingAction.LOCAL

        return RoutingAction.CLOUD
