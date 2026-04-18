from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from .context import RoutingContext
from .actions import RoutingAction


class RoutingPolicy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def score(self, context: RoutingContext) -> dict[str, float]:
        pass

    @abstractmethod
    def decide(self, scores: dict[str, float]) -> RoutingAction:
        pass


@dataclass
class PolicyResult:
    action: RoutingAction
    scores: dict[str, float]
    policy_name: str
    reason: Optional[str] = None
