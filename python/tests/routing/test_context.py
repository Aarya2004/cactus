import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.context import RoutingContext


class TestRoutingContext(unittest.TestCase):

    def test_creates_with_required_fields(self):
        ctx = RoutingContext(
            query="Can I take ibuprofen?",
            confidence=0.85,
        )
        self.assertEqual(ctx.query, "Can I take ibuprofen?")
        self.assertEqual(ctx.confidence, 0.85)

    def test_defaults_for_optional_fields(self):
        ctx = RoutingContext(query="test", confidence=0.5)
        self.assertEqual(ctx.latency_budget_ms, 1000)
        self.assertEqual(ctx.battery_pct, 100.0)
        self.assertEqual(ctx.network_quality, "fast")
        self.assertEqual(ctx.metadata, {})

    def test_custom_optional_fields(self):
        ctx = RoutingContext(
            query="test",
            confidence=0.7,
            latency_budget_ms=200,
            battery_pct=15.0,
            network_quality="slow",
            metadata={"clinical_severity": "MAJOR"},
        )
        self.assertEqual(ctx.latency_budget_ms, 200)
        self.assertEqual(ctx.battery_pct, 15.0)
        self.assertEqual(ctx.network_quality, "slow")
        self.assertEqual(ctx.metadata["clinical_severity"], "MAJOR")

    def test_confidence_clamped_to_valid_range(self):
        ctx_low = RoutingContext(query="test", confidence=-0.5)
        ctx_high = RoutingContext(query="test", confidence=1.5)
        self.assertEqual(ctx_low.confidence, 0.0)
        self.assertEqual(ctx_high.confidence, 1.0)

    def test_battery_clamped_to_valid_range(self):
        ctx_low = RoutingContext(query="test", confidence=0.5, battery_pct=-10)
        ctx_high = RoutingContext(query="test", confidence=0.5, battery_pct=150)
        self.assertEqual(ctx_low.battery_pct, 0.0)
        self.assertEqual(ctx_high.battery_pct, 100.0)

    def test_network_quality_validates(self):
        with self.assertRaises(ValueError):
            RoutingContext(query="test", confidence=0.5, network_quality="invalid")

    def test_immutable_after_creation(self):
        ctx = RoutingContext(query="test", confidence=0.5)
        with self.assertRaises(AttributeError):
            ctx.confidence = 0.9


if __name__ == "__main__":
    unittest.main()
