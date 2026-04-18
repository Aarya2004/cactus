"""Integration helpers for wiring CactusRouter into completion flows."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .context import RoutingContext
from .actions import RoutingAction
from .policy import PolicyResult
from .router import CactusRouter
from .pii import PIIStripper, PIIProfile
from .signals import SignalProvider, default_signals


@dataclass
class RoutedCompletion:
    response: str
    action: RoutingAction
    scores: dict[str, float]
    policy_name: str
    reason: Optional[str] = None
    anonymized_query: Optional[str] = None


class RoutedCompletionHandler:
    def __init__(
        self,
        router: CactusRouter,
        local_complete: Callable[[str], tuple[str, float]],
        cloud_complete: Optional[Callable[[str], str]] = None,
        pii_stripper: Optional[PIIStripper] = None,
        signal_provider: Optional[SignalProvider] = None,
    ):
        self._router = router
        self._local = local_complete
        self._cloud = cloud_complete
        self._stripper = pii_stripper or PIIStripper()
        self._signals = signal_provider or default_signals

    def complete(
        self,
        query: str,
        pii_profile: Optional[PIIProfile] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RoutedCompletion:
        local_response, confidence = self._local(query)

        context = RoutingContext(
            query=query,
            confidence=confidence,
            battery_pct=self._signals.battery_pct(),
            network_quality=self._signals.network_quality(),
            latency_budget_ms=self._signals.latency_budget_ms(),
            metadata=metadata or {},
        )

        result = self._router.route(context)

        if result.action == RoutingAction.LOCAL:
            return RoutedCompletion(
                response=local_response,
                action=result.action,
                scores=result.scores,
                policy_name=result.policy_name,
                reason=result.reason,
            )

        if result.action == RoutingAction.REFUSE:
            return RoutedCompletion(
                response="I cannot answer this question with the current settings.",
                action=result.action,
                scores=result.scores,
                policy_name=result.policy_name,
                reason=result.reason,
            )

        profile = pii_profile or PIIProfile()
        anonymized = self._stripper.strip(query, profile)

        if result.action in (RoutingAction.CLOUD, RoutingAction.CLOUD_PII_STRIP):
            if not self._cloud:
                return RoutedCompletion(
                    response=local_response,
                    action=RoutingAction.LOCAL,
                    scores=result.scores,
                    policy_name=result.policy_name,
                    reason="Cloud unavailable, falling back to local",
                    anonymized_query=anonymized if result.action == RoutingAction.CLOUD_PII_STRIP else None,
                )

            cloud_query = anonymized if result.action == RoutingAction.CLOUD_PII_STRIP else query
            cloud_response = self._cloud(cloud_query)

            return RoutedCompletion(
                response=cloud_response,
                action=result.action,
                scores=result.scores,
                policy_name=result.policy_name,
                reason=result.reason,
                anonymized_query=anonymized if result.action == RoutingAction.CLOUD_PII_STRIP else None,
            )

        if result.action == RoutingAction.CASCADE:
            if not self._cloud:
                return RoutedCompletion(
                    response=local_response,
                    action=RoutingAction.LOCAL,
                    scores=result.scores,
                    policy_name=result.policy_name,
                    reason="Cloud unavailable, cascade fell back to local only",
                )

            cloud_response = self._cloud(anonymized)

            return RoutedCompletion(
                response=f"{local_response}\n\n[Verified by cloud: {cloud_response}]",
                action=result.action,
                scores=result.scores,
                policy_name=result.policy_name,
                reason=result.reason,
                anonymized_query=anonymized,
            )

        return RoutedCompletion(
            response=local_response,
            action=RoutingAction.LOCAL,
            scores=result.scores,
            policy_name=result.policy_name,
            reason="Unknown action, defaulted to local",
        )
