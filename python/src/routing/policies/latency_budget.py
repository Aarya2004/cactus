from ..context import RoutingContext
from ..actions import RoutingAction
from ..policy import RoutingPolicy

NETWORK_LATENCY_ESTIMATES_MS = {
    "fast": 50,
    "slow": 500,
    "offline": float("inf"),
}


class LatencyBudgetPolicy(RoutingPolicy):
    """Routes based on whether local or cloud can meet the latency budget.

    Compares estimated local inference latency and estimated cloud round-trip
    latency against the caller's latency budget. Picks the one that fits;
    falls back to confidence when both (or neither) fit.
    """

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
            local_latency_pressure = 1.0
        else:
            latency_pressure = min(
                1.0, network_latency / context.latency_budget_ms
            )
            local_latency_pressure = min(
                1.0, self._local_latency_ms / context.latency_budget_ms
            )

        network_score = 1.0 if context.network_quality == "fast" else (
            0.5 if context.network_quality == "slow" else 0.0
        )

        return {
            "confidence": context.confidence,
            "latency_pressure": latency_pressure,
            "local_latency_pressure": local_latency_pressure,
            "network_score": network_score,
        }

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["network_score"] == 0.0:
            return RoutingAction.LOCAL

        local_fits = scores["local_latency_pressure"] < 1.0
        cloud_fits = scores["latency_pressure"] < 0.8

        if not local_fits and cloud_fits:
            return RoutingAction.CLOUD

        if not cloud_fits:
            return RoutingAction.LOCAL

        if scores["confidence"] >= self._confidence_threshold:
            return RoutingAction.LOCAL

        return RoutingAction.CLOUD
