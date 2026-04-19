import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.context import RoutingContext
from src.routing.actions import RoutingAction
from src.routing.policies.threshold import ThresholdPolicy
from src.routing.policies.battery_aware import BatteryAwarePolicy
from src.routing.policies.latency_budget import LatencyBudgetPolicy


class TestThresholdPolicy(unittest.TestCase):

    def test_high_confidence_routes_local(self):
        policy = ThresholdPolicy(confidence_threshold=0.7)
        ctx = RoutingContext(query="test", confidence=0.85)
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_low_confidence_routes_cloud(self):
        policy = ThresholdPolicy(confidence_threshold=0.7)
        ctx = RoutingContext(query="test", confidence=0.5)
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD)

    def test_exact_threshold_routes_local(self):
        policy = ThresholdPolicy(confidence_threshold=0.7)
        ctx = RoutingContext(query="test", confidence=0.7)
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_custom_threshold(self):
        policy = ThresholdPolicy(confidence_threshold=0.9)
        ctx = RoutingContext(query="test", confidence=0.85)
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD)

    def test_default_threshold_is_0_7(self):
        policy = ThresholdPolicy()
        self.assertEqual(policy._threshold, 0.7)

    def test_threshold_none_defers_to_model_default_in_context(self):
        """When threshold=None, ThresholdPolicy reads the model-specific default
        from context.metadata['model_default_confidence_threshold']. This lets
        callers preserve the engine's per-model default behavior instead of
        forcing a hardcoded 0.7 on every model."""
        policy = ThresholdPolicy(confidence_threshold=None)

        ctx_below = RoutingContext(
            query="test",
            confidence=0.6,
            metadata={"model_default_confidence_threshold": 0.8},
        )
        ctx_above = RoutingContext(
            query="test",
            confidence=0.85,
            metadata={"model_default_confidence_threshold": 0.8},
        )

        self.assertEqual(policy.decide(policy.score(ctx_below)), RoutingAction.CLOUD)
        self.assertEqual(policy.decide(policy.score(ctx_above)), RoutingAction.LOCAL)

    def test_threshold_none_falls_back_to_0_7_without_metadata(self):
        policy = ThresholdPolicy(confidence_threshold=None)
        ctx = RoutingContext(query="test", confidence=0.75)
        self.assertEqual(policy.decide(policy.score(ctx)), RoutingAction.LOCAL)


class TestBatteryAwarePolicy(unittest.TestCase):

    def test_low_battery_prefers_local(self):
        policy = BatteryAwarePolicy(low_battery_threshold=20.0)
        ctx = RoutingContext(query="test", confidence=0.5, battery_pct=15.0)
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_high_battery_defers_to_confidence(self):
        policy = BatteryAwarePolicy(low_battery_threshold=20.0)
        ctx_high_conf = RoutingContext(query="test", confidence=0.9, battery_pct=80.0)
        ctx_low_conf = RoutingContext(query="test", confidence=0.3, battery_pct=80.0)

        self.assertEqual(policy.decide(policy.score(ctx_high_conf)), RoutingAction.LOCAL)
        self.assertEqual(policy.decide(policy.score(ctx_low_conf)), RoutingAction.CLOUD)

    def test_critical_battery_always_local(self):
        policy = BatteryAwarePolicy(critical_battery_threshold=5.0)
        ctx = RoutingContext(query="test", confidence=0.1, battery_pct=3.0)
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_scores_include_battery(self):
        policy = BatteryAwarePolicy()
        ctx = RoutingContext(query="test", confidence=0.8, battery_pct=45.0)
        scores = policy.score(ctx)
        self.assertIn("battery_pct", scores)
        self.assertEqual(scores["battery_pct"], 0.45)


class TestLatencyBudgetPolicy(unittest.TestCase):

    def test_tight_budget_slow_network_routes_local(self):
        policy = LatencyBudgetPolicy()
        ctx = RoutingContext(
            query="test",
            confidence=0.5,
            latency_budget_ms=100,
            network_quality="slow",
        )
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_generous_budget_fast_network_defers_to_confidence(self):
        policy = LatencyBudgetPolicy()
        ctx_high = RoutingContext(
            query="test",
            confidence=0.9,
            latency_budget_ms=2000,
            network_quality="fast",
        )
        ctx_low = RoutingContext(
            query="test",
            confidence=0.3,
            latency_budget_ms=2000,
            network_quality="fast",
        )
        self.assertEqual(policy.decide(policy.score(ctx_high)), RoutingAction.LOCAL)
        self.assertEqual(policy.decide(policy.score(ctx_low)), RoutingAction.CLOUD)

    def test_offline_always_local(self):
        policy = LatencyBudgetPolicy()
        ctx = RoutingContext(
            query="test",
            confidence=0.1,
            network_quality="offline",
        )
        scores = policy.score(ctx)
        action = policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_scores_include_latency_pressure(self):
        policy = LatencyBudgetPolicy()
        ctx = RoutingContext(
            query="test",
            confidence=0.7,
            latency_budget_ms=500,
            network_quality="fast",
        )
        scores = policy.score(ctx)
        self.assertIn("latency_pressure", scores)
        self.assertIn("network_score", scores)

    def test_local_latency_exceeds_budget_routes_cloud(self):
        """If on-device inference can't meet the latency budget, cloud wins
        despite network overhead — the budget is the constraint, not the device."""
        policy = LatencyBudgetPolicy(local_latency_ms=2000)
        ctx = RoutingContext(
            query="test",
            confidence=0.3,
            latency_budget_ms=500,
            network_quality="fast",
        )
        scores = policy.score(ctx)
        self.assertIn("local_latency_pressure", scores)
        self.assertEqual(policy.decide(scores), RoutingAction.CLOUD)

    def test_local_latency_within_budget_prefers_local(self):
        policy = LatencyBudgetPolicy(local_latency_ms=100)
        ctx = RoutingContext(
            query="test",
            confidence=0.9,
            latency_budget_ms=500,
            network_quality="fast",
        )
        scores = policy.score(ctx)
        self.assertEqual(policy.decide(scores), RoutingAction.LOCAL)


if __name__ == "__main__":
    unittest.main()
