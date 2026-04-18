from collections import Counter
from typing import Optional

from .context import RoutingContext
from .actions import RoutingAction
from .policy import RoutingPolicy, PolicyResult


class CactusRouter:
    def __init__(self):
        self._policies: list[tuple[RoutingPolicy, float]] = []

    def register(self, policy: RoutingPolicy, weight: float = 1.0) -> None:
        self._policies.append((policy, weight))

    def unregister(self, name: str) -> None:
        self._policies = [(p, w) for p, w in self._policies if p.name != name]

    def clear(self) -> None:
        self._policies.clear()

    @property
    def policies(self) -> list[tuple[RoutingPolicy, float]]:
        return list(self._policies)

    def route(self, context: RoutingContext) -> PolicyResult:
        if not self._policies:
            return PolicyResult(
                action=RoutingAction.LOCAL,
                scores={},
                policy_name="default",
                reason="No policies registered, defaulting to LOCAL",
            )

        action_weights: Counter[RoutingAction] = Counter()
        all_scores: dict[str, float] = {}
        reasons: list[str] = []

        for policy, weight in self._policies:
            scores = policy.score(context)
            action = policy.decide(scores)

            for key, val in scores.items():
                all_scores[f"{policy.name}.{key}"] = val

            action_weights[action] += weight
            reasons.append(f"{policy.name}→{action.value}")

        winning_action = action_weights.most_common(1)[0][0]

        return PolicyResult(
            action=winning_action,
            scores=all_scores,
            policy_name=",".join(p.name for p, _ in self._policies),
            reason="; ".join(reasons),
        )
