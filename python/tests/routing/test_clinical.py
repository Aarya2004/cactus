import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.context import RoutingContext
from src.routing.actions import RoutingAction
from src.routing.policies.clinical import ClinicalPolicy


class TestClinicalPolicy(unittest.TestCase):

    def setUp(self):
        self.policy = ClinicalPolicy()

    def test_high_confidence_no_interaction_routes_local(self):
        ctx = RoutingContext(
            query="What time should I take my vitamins?",
            confidence=0.85,
            metadata={"clinical_severity": "NONE"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_low_confidence_routes_cloud_pii_strip(self):
        ctx = RoutingContext(
            query="Can I take this new medication?",
            confidence=0.3,
            metadata={"clinical_severity": "NONE"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD_PII_STRIP)

    def test_major_interaction_confident_routes_cascade(self):
        ctx = RoutingContext(
            query="Can I take ibuprofen?",
            confidence=0.8,
            metadata={"clinical_severity": "MAJOR"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.CASCADE)

    def test_major_interaction_low_confidence_routes_cloud(self):
        ctx = RoutingContext(
            query="Can I take this with warfarin?",
            confidence=0.35,
            metadata={"clinical_severity": "MAJOR"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD_PII_STRIP)

    def test_moderate_interaction_routes_local(self):
        ctx = RoutingContext(
            query="Is grapefruit okay with my statin?",
            confidence=0.75,
            metadata={"clinical_severity": "MODERATE"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_ambiguous_query_routes_cloud(self):
        ctx = RoutingContext(
            query="Is this safe?",
            confidence=0.5,
            metadata={"query_ambiguous": True},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD_PII_STRIP)

    def test_high_pii_density_strips_before_cloud(self):
        ctx = RoutingContext(
            query="I'm Sarah, 62, taking lisinopril 10mg",
            confidence=0.35,
            metadata={"pii_density": 0.8},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD_PII_STRIP)

    def test_offline_always_local(self):
        ctx = RoutingContext(
            query="Is this interaction dangerous?",
            confidence=0.3,
            network_quality="offline",
            metadata={"clinical_severity": "MAJOR"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_critical_battery_prefers_local(self):
        ctx = RoutingContext(
            query="Can I take this?",
            confidence=0.4,
            battery_pct=3.0,
            metadata={"clinical_severity": "MINOR"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.LOCAL)

    def test_consent_tier_strict_refuses_cloud(self):
        ctx = RoutingContext(
            query="Complex medical question",
            confidence=0.3,
            metadata={"consent_tier": "strict"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.REFUSE)

    def test_consent_tier_standard_allows_cloud(self):
        ctx = RoutingContext(
            query="Complex medical question",
            confidence=0.3,
            metadata={"consent_tier": "standard"},
        )
        scores = self.policy.score(ctx)
        action = self.policy.decide(scores)
        self.assertEqual(action, RoutingAction.CLOUD_PII_STRIP)

    def test_scores_include_all_dimensions(self):
        ctx = RoutingContext(
            query="test",
            confidence=0.7,
            battery_pct=50.0,
            latency_budget_ms=500,
            network_quality="fast",
            metadata={
                "clinical_severity": "MODERATE",
                "pii_density": 0.3,
            },
        )
        scores = self.policy.score(ctx)
        self.assertIn("confidence", scores)
        self.assertIn("clinical_severity", scores)
        self.assertIn("battery_score", scores)
        self.assertIn("network_score", scores)
        self.assertIn("pii_density", scores)

    def test_default_metadata_values(self):
        ctx = RoutingContext(query="simple question", confidence=0.8)
        scores = self.policy.score(ctx)
        self.assertEqual(scores["clinical_severity"], 0.0)
        self.assertEqual(scores["pii_density"], 0.0)


if __name__ == "__main__":
    unittest.main()
