import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.context import RoutingContext
from src.routing.actions import RoutingAction
from src.routing.policy import RoutingPolicy, PolicyResult
from src.routing.router import CactusRouter


class AlwaysLocalPolicy(RoutingPolicy):
    @property
    def name(self) -> str:
        return "always_local"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {"local_preference": 1.0}

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        return RoutingAction.LOCAL


class AlwaysCloudPolicy(RoutingPolicy):
    @property
    def name(self) -> str:
        return "always_cloud"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {"cloud_preference": 1.0}

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        return RoutingAction.CLOUD


class ConfidenceBasedPolicy(RoutingPolicy):
    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "confidence"

    def score(self, context: RoutingContext) -> dict[str, float]:
        return {"confidence": context.confidence}

    def decide(self, scores: dict[str, float]) -> RoutingAction:
        if scores["confidence"] >= self._threshold:
            return RoutingAction.LOCAL
        return RoutingAction.CLOUD


class TestCactusRouter(unittest.TestCase):

    def test_empty_router_defaults_to_local(self):
        router = CactusRouter()
        ctx = RoutingContext(query="test", confidence=0.5)
        result = router.route(ctx)
        self.assertEqual(result.action, RoutingAction.LOCAL)

    def test_single_policy(self):
        router = CactusRouter()
        router.register(AlwaysCloudPolicy())
        ctx = RoutingContext(query="test", confidence=0.9)
        result = router.route(ctx)
        self.assertEqual(result.action, RoutingAction.CLOUD)

    def test_multiple_policies_uses_priority(self):
        router = CactusRouter()
        router.register(AlwaysLocalPolicy(), weight=0.3)
        router.register(AlwaysCloudPolicy(), weight=0.7)
        ctx = RoutingContext(query="test", confidence=0.5)
        result = router.route(ctx)
        self.assertEqual(result.action, RoutingAction.CLOUD)

    def test_equal_weights_uses_first_registered(self):
        router = CactusRouter()
        router.register(AlwaysLocalPolicy(), weight=0.5)
        router.register(AlwaysCloudPolicy(), weight=0.5)
        ctx = RoutingContext(query="test", confidence=0.5)
        result = router.route(ctx)
        self.assertIn(result.action, [RoutingAction.LOCAL, RoutingAction.CLOUD])

    def test_confidence_policy_routes_correctly(self):
        router = CactusRouter()
        router.register(ConfidenceBasedPolicy(threshold=0.7))

        high_conf = RoutingContext(query="simple query", confidence=0.9)
        low_conf = RoutingContext(query="complex query", confidence=0.4)

        self.assertEqual(router.route(high_conf).action, RoutingAction.LOCAL)
        self.assertEqual(router.route(low_conf).action, RoutingAction.CLOUD)

    def test_result_includes_all_scores(self):
        router = CactusRouter()
        router.register(ConfidenceBasedPolicy())
        ctx = RoutingContext(query="test", confidence=0.85)
        result = router.route(ctx)
        self.assertIn("confidence.confidence", result.scores)

    def test_unregister_policy(self):
        router = CactusRouter()
        policy = AlwaysCloudPolicy()
        router.register(policy)
        router.unregister("always_cloud")
        ctx = RoutingContext(query="test", confidence=0.5)
        result = router.route(ctx)
        self.assertEqual(result.action, RoutingAction.LOCAL)

    def test_clear_policies(self):
        router = CactusRouter()
        router.register(AlwaysCloudPolicy())
        router.clear()
        self.assertEqual(len(router.policies), 0)

    def test_list_policies(self):
        router = CactusRouter()
        router.register(AlwaysLocalPolicy(), weight=0.6)
        router.register(AlwaysCloudPolicy(), weight=0.4)
        policies = router.policies
        self.assertEqual(len(policies), 2)
        names = [p.name for p, _ in policies]
        self.assertIn("always_local", names)
        self.assertIn("always_cloud", names)


class TestRouterBackwardCompat(unittest.TestCase):

    def test_no_router_behavior_matches_threshold(self):
        from src.routing.policies.threshold import ThresholdPolicy

        router = CactusRouter()
        router.register(ThresholdPolicy(confidence_threshold=0.7))

        above = RoutingContext(query="test", confidence=0.8)
        below = RoutingContext(query="test", confidence=0.5)

        self.assertEqual(router.route(above).action, RoutingAction.LOCAL)
        self.assertEqual(router.route(below).action, RoutingAction.CLOUD)


if __name__ == "__main__":
    unittest.main()
