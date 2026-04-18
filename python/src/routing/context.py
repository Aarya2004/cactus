from dataclasses import dataclass, field
from typing import Any

VALID_NETWORK_QUALITIES = frozenset({"offline", "slow", "fast"})


def _clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))


@dataclass(frozen=True)
class RoutingContext:
    query: str
    confidence: float
    latency_budget_ms: int = 1000
    battery_pct: float = 100.0
    network_quality: str = "fast"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "confidence", _clamp(self.confidence, 0.0, 1.0))
        object.__setattr__(self, "battery_pct", _clamp(self.battery_pct, 0.0, 100.0))

        if self.network_quality not in VALID_NETWORK_QUALITIES:
            raise ValueError(
                f"network_quality must be one of {VALID_NETWORK_QUALITIES}, "
                f"got '{self.network_quality}'"
            )
