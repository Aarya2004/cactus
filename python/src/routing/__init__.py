"""Cactus Routing Framework — pluggable policy-based routing for local/cloud decisions."""

from .context import RoutingContext
from .actions import RoutingAction
from .policy import RoutingPolicy, PolicyResult
from .router import CactusRouter
from .pii import PIIStripper, PIIProfile
from .signals import SignalProvider, default_signals
from .integration import (
    RoutedCompletionHandler,
    RoutedCompletion,
    CloudPayloadMode,
)

__all__ = [
    "RoutingContext",
    "RoutingAction",
    "RoutingPolicy",
    "PolicyResult",
    "CactusRouter",
    "PIIStripper",
    "PIIProfile",
    "SignalProvider",
    "default_signals",
    "RoutedCompletionHandler",
    "RoutedCompletion",
    "CloudPayloadMode",
]
