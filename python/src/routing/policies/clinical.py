from ..context import RoutingContext
from ..actions import RoutingAction
from ..policy import RoutingPolicy

SEVERITY_SCORES = {
    "NONE": 0.0,
    "MINOR": 0.3,
    "MODERATE": 0.6,
    "MAJOR": 1.0,
}


class ClinicalPolicy(RoutingPolicy):
    def __init__(
        self,
        confidence_threshold_high: float = 0.7,
        confidence_threshold_low: float = 0.4,
        critical_battery_pct: float = 5.0,
    ):
        self._conf_high = confidence_threshold_high
        self._conf_low = confidence_threshold_low
        self._critical_battery = critical_battery_pct

    @property
    def name(self) -> str:
        return "clinical"

    def score(self, context: RoutingContext) -> dict[str, float]:
        severity_str = context.metadata.get("clinical_severity", "NONE")
        severity = SEVERITY_SCORES.get(severity_str, 0.0)

        pii_density = context.metadata.get("pii_density", 0.0)

        network_score = 1.0 if context.network_quality == "fast" else (
            0.5 if context.network_quality == "slow" else 0.0
        )

        consent_tier = context.metadata.get("consent_tier", "standard")
        consent_strict = 1.0 if consent_tier == "strict" else 0.0

        return {
            "confidence": context.confidence,
            "clinical_severity": severity,
            "pii_density": pii_density,
            "battery_score": context.battery_pct / 100.0,
            "network_score": network_score,
            "query_ambiguous": 1.0 if context.metadata.get("query_ambiguous") else 0.0,
            "consent_strict": consent_strict,
        }

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        confidence = scores["confidence"]
        severity = scores["clinical_severity"]
        network = scores["network_score"]
        battery = scores["battery_score"]
        ambiguous = scores["query_ambiguous"]
        consent_strict = scores.get("consent_strict", 0.0)

        if network == 0.0:
            return RoutingAction.LOCAL

        if battery <= self._critical_battery / 100.0:
            return RoutingAction.LOCAL

        if consent_strict > 0.5 and confidence < self._conf_high:
            return RoutingAction.REFUSE

        if confidence >= self._conf_high and severity < SEVERITY_SCORES["MAJOR"]:
            return RoutingAction.LOCAL

        if confidence < self._conf_low or ambiguous > 0.5:
            return RoutingAction.CLOUD_PII_STRIP

        if severity >= SEVERITY_SCORES["MAJOR"] and confidence >= self._conf_high:
            return RoutingAction.CASCADE

        return RoutingAction.LOCAL
