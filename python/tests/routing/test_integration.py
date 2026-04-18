import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.routing.context import RoutingContext
from src.routing.actions import RoutingAction
from src.routing.router import CactusRouter
from src.routing.pii import PIIProfile
from src.routing.policies.threshold import ThresholdPolicy
from src.routing.policies.clinical import ClinicalPolicy
from src.routing.signals import SignalProvider
from src.routing.integration import RoutedCompletionHandler, RoutedCompletion


def mock_local_complete(query: str) -> tuple[str, float]:
    if "simple" in query.lower():
        return ("Simple answer from local model", 0.9)
    if "complex" in query.lower():
        return ("Best-effort answer from local model", 0.3)
    return ("Local answer", 0.7)


def mock_cloud_complete(query: str) -> str:
    return f"Cloud response for: {query}"


class TestRoutedCompletionHandler(unittest.TestCase):

    def setUp(self):
        self.router = CactusRouter()
        self.router.register(ThresholdPolicy(confidence_threshold=0.7))

        self.signals = SignalProvider(
            battery_fn=lambda: 80.0,
            network_fn=lambda: "fast",
            latency_fn=lambda: 1000,
        )

        self.handler = RoutedCompletionHandler(
            router=self.router,
            local_complete=mock_local_complete,
            cloud_complete=mock_cloud_complete,
            signal_provider=self.signals,
        )

    def test_high_confidence_uses_local(self):
        result = self.handler.complete("This is a simple question")
        self.assertEqual(result.action, RoutingAction.LOCAL)
        self.assertIn("Simple answer", result.response)

    def test_low_confidence_uses_cloud(self):
        result = self.handler.complete("This is a complex question")
        self.assertEqual(result.action, RoutingAction.CLOUD)
        self.assertIn("Cloud response", result.response)

    def test_cloud_unavailable_falls_back_to_local(self):
        handler = RoutedCompletionHandler(
            router=self.router,
            local_complete=mock_local_complete,
            cloud_complete=None,
            signal_provider=self.signals,
        )
        result = handler.complete("This is a complex question")
        self.assertEqual(result.action, RoutingAction.LOCAL)
        self.assertIn("Best-effort", result.response)

    def test_pii_strip_anonymizes_query(self):
        router = CactusRouter()
        router.register(ClinicalPolicy())

        handler = RoutedCompletionHandler(
            router=router,
            local_complete=lambda q: ("Local", 0.3),
            cloud_complete=mock_cloud_complete,
            signal_provider=self.signals,
        )

        profile = PIIProfile(
            patient_name="John Doe",
            medications=["lisinopril"],
        )

        result = handler.complete(
            "John Doe takes lisinopril 10mg",
            pii_profile=profile,
        )

        self.assertEqual(result.action, RoutingAction.CLOUD_PII_STRIP)
        self.assertIsNotNone(result.anonymized_query)
        self.assertNotIn("John Doe", result.anonymized_query)
        self.assertNotIn("lisinopril", result.anonymized_query)
        self.assertIn("[PATIENT]", result.anonymized_query)
        self.assertIn("[DRUG_A]", result.anonymized_query)

    def test_refuse_returns_safe_message(self):
        router = CactusRouter()
        router.register(ClinicalPolicy())

        handler = RoutedCompletionHandler(
            router=router,
            local_complete=lambda q: ("Local", 0.3),
            cloud_complete=mock_cloud_complete,
            signal_provider=self.signals,
        )

        result = handler.complete(
            "Complex medical question",
            metadata={"consent_tier": "strict"},
        )

        self.assertEqual(result.action, RoutingAction.REFUSE)
        self.assertIn("cannot answer", result.response.lower())

    def test_cascade_includes_both_responses(self):
        router = CactusRouter()
        router.register(ClinicalPolicy())

        handler = RoutedCompletionHandler(
            router=router,
            local_complete=lambda q: ("Local says safe", 0.8),
            cloud_complete=mock_cloud_complete,
            signal_provider=self.signals,
        )

        result = handler.complete(
            "Can I take ibuprofen?",
            metadata={"clinical_severity": "MAJOR"},
        )

        self.assertEqual(result.action, RoutingAction.CASCADE)
        self.assertIn("Local says safe", result.response)
        self.assertIn("Verified by cloud", result.response)

    def test_result_includes_scores(self):
        result = self.handler.complete("Test query")
        self.assertIsInstance(result.scores, dict)
        self.assertGreater(len(result.scores), 0)

    def test_offline_forces_local(self):
        offline_signals = SignalProvider(
            battery_fn=lambda: 80.0,
            network_fn=lambda: "offline",
            latency_fn=lambda: 1000,
        )

        router = CactusRouter()
        router.register(ClinicalPolicy())

        handler = RoutedCompletionHandler(
            router=router,
            local_complete=lambda q: ("Offline local", 0.3),
            cloud_complete=mock_cloud_complete,
            signal_provider=offline_signals,
        )

        result = handler.complete("Complex question")
        self.assertEqual(result.action, RoutingAction.LOCAL)


if __name__ == "__main__":
    unittest.main()
